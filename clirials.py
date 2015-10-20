# ui for app
#   add
#       add name [-s SEASONS] [-e EPISODES]
#   delete
#       name
#   set
#       name [-e SEASON EPISODE]
#   update
#       name season [-e EPISODES] [-a | -b | -c]
#   status
#       [name]
#   save
#   exit
#
# data = OrderedDict {
#                       'cur' : 'seriesN',
#                       'series1' : Series(),
#                       'series2' : Series(),..
#                   }

import argparse
import cmd
import os.path
import pickle
import collections
import statistics

class ExitSuppressorException(Exception):
    """Exception to prevent the argparse from exiting because of an error"""


class Parser(argparse.ArgumentParser):
    """extends ArgumentParser"""

    def error(self, message):
        raise ExitSuppressorException(message)


def lazyprop(fn):
    """decorator function to initialize parsers lazily."""
    attr_name = "_lazy_" + fn.__name__
    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazyprop


class Parsers():
    """Parser holder"""

    @lazyprop
    def addp(self):
        parser = Parser(description='Add a Series to start tracking it',prog='add',
                        add_help=False, usage='%(prog)s name [-s SEASONS] [-e EPISODES]')
        parser.add_argument('name', action='store', nargs='+', help='name of the Series')
        parser.add_argument('-s', dest='seasons', default=1, type=int,
                            help='No. of seasons in the Series')
        parser.add_argument('-e', dest='episodes', default=10, type=int,
                            help='no. of episodes per season')
        return parser

    @lazyprop
    def deletep(self):
        parser = Parser(description='Delete a Series to stop tracking it', prog='delete',
                        add_help=False, usage='%(prog)s name')
        parser.add_argument('name', action='store', nargs='*', default='',
                           help='name of the Series')
        return parser

    @lazyprop
    def setp(self):
        parser = Parser(description='Set the desired episode', add_help=False,
                        conflict_handler='resolve', prog='set',
                        usage='%(prog)s [-e SEASON EPISODE]')
        parser.add_argument('name', action='store', nargs='*', default='',
                           help='name of the Series')
        parser.add_argument('-e', dest='episode', default=[], type=int, nargs=2,
                            help='the last watched Episode to set the pointer to')
        return parser

    @lazyprop
    def updatep(self):
        parser = Parser(description='Update the index table', prog='update',
                        add_help=False, conflict_handler='resolve',
                        usage='update name [-a | -d | -c] [-e EPISODES]')
        parser.add_argument('name', action='store', nargs='*', default='',
                           help='name of the Series')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('-a', action='store_true', default=False, dest='add',
                           help='add a season')
        group.add_argument('-d', action='store_true', default=False, dest='delete',
                           help='delete a season')
        group.add_argument('-c', action='store_true', default=False, dest='change',
                           help='change number of episodes for a season')
        parser.add_argument('-e', dest='episodes', type=int, help='episodes in season',
                            default=0)
        return parser

    @lazyprop
    def statusp(self):
        parser = Parser(description='Print the index table', prog='status',
                        add_help=False, usage='%(prog)s name [-l]')
        parser.add_argument('name', action='store', nargs='*', default='',
                           help='name of the Series')
        parser.add_argument('-l', action='count', default=0, help='show legacy Series')
        return parser

################################################################
#
# Class for data :
#
class Series():
    def __init__(self, series_name):
        self.name = series_name
        self.seasons = []
        self.cur_season = 1
        self.last_episode = 0
        self.deleted = False

    @property
    def next_season(self):
        if self.has_episode(self.cur_season+1, 0):
            return self.cur_season + 1
        return False


    def add_season(self, episodes):
        self.seasons.append(episodes)

    def has_episode(self, season, episode):
        return (0 < season <= len(self.seasons)) and \
                        (0 <= episode <= self.seasons[season-1])
#
#
##################################################################



class Clirials(cmd.Cmd):
    """A CLI for manipulating database of Serials"""

    def __init__(self):
        self.prompt = 'clirials>'
        super().__init__(self)
        self.counter = 0
        self.lastcmd_was_save = True


    def cmdloop(self, intro='A CLI for manipulating database of Serials'):
        super().cmdloop(intro)

    def preloop(self):
        if not os.path.exists('data.pickle'):           # for the first time app is run
            data = collections.OrderedDict()
            data['cur'] = ''
            with open('data.pickle', 'wb') as f:
                pickle.dump(data, f)
        with open('data.pickle', 'rb') as f:            # load the data
            self.data = pickle.load(f)
        self.parsers = Parsers()

    def postloop(self):
        if not self.lastcmd_was_save:
            save_on_exit = input("Would you like to save the changes(y/n)?")
            if save_on_exit == 'y':
                print('Saving...')
                self._save()

    def postcmd(self, stop, line):
        last_command = self.lastcmd.split(maxsplit=1)[0]
        # 'exit' included because 'Autosaving... ' at exit doesn't look good
        if last_command in ['exit', 'save']:
            self.counter = 0
            return stop
        elif last_command in ['add', 'delete', 'set', 'update']:
            self.lastcmd_was_save = False
            self.counter += 1                   # change in data --> counter++
        if self.counter > 4:
            print('Autosaving...')
            self._save()
        return stop

    def _save(self):
        with open('data.pickle', 'wb') as f:
            pickle.dump(self.data, f)
        self.counter = 0
        self.lastcmd_was_save = True

    def emptyline(self):
        pass

    # this is not working
    def completedefault(self, text, line, begidx, endidx):
        series_list_names = list(self.data.keys())
        series_list_names.remove('cur')
        if not text:
            completions = series_list_names[:]
        else:
            completions = [s for s in series_list_names if s.startswith(text)]
        return completions

    def do_add(self, args):
        try:
            arguments = self.parsers.addp.parse_args(args.split())
        except ExitSuppressorException as e:
            print(e)
            self.lastcmd = 'not_exec'
            return
        arguments.name = ' '.join(arguments.name).title()
        if arguments.name in self.data:
            if self.data[arguments.name].deleted:       # deleted series
                print('\n\t' + arguments.name + ' was perviously deleted')
                print('\n\t' + 'Use "status -l" command to view all legacy Series\n')
            else:
                print('\n\t' + arguments.name + ' is already being tracked.')
                print('\n\t' + 'Use "update -a" to add more seasons to a Series\n')
            self.lastcmd = 'not_exec'
            return
        if arguments.seasons<1 or arguments.episodes<1:
            print('\nInvalid values for Seasons or Episodes\n')
            self.lastcmd = 'not_exec'
            return
        new_series = Series(arguments.name)
        new_series.seasons = [arguments.episodes] * arguments.seasons
        self.data[arguments.name] = new_series
        if len(self.data) == 2:         # 'cur' : '' is present by default
            self.data['cur'] = new_series.name

    def help_add(self):
        self.parsers.addp.print_help()

    def complete_add(self):
        pass

    def _parse_args(self, args, parser):
        # return False on failure
        try:
            arguments = parser.parse_args(args.split())
        except ExitSuppressorException as e:
            print(e)
            self.lastcmd = 'not_exec'
            return False
        arguments.name = ' '.join(arguments.name).title().strip()
        if arguments.name:
            if not arguments.name in self.data:
                print('\n\t Series not found: ' + arguments.name)
                print()
                self.lastcmd = 'not_exec'
                return False
            else:
                return arguments
        if parser is self.parsers.statusp:        # Series is optional for status
            return arguments
        print('\n\tRequired Arguments : name \n')
        self.lastcmd = 'not_exec'
        return False


    def do_delete(self, args):
        arguments = self._parse_args(args, self.parsers.deletep)
        if not arguments:               # check for failure
            return
        if self.data['cur'] == arguments.name:
            print('\n\t' + arguments.name + ' cannot be deleted : current series \n')
            self.lastcmd = 'not_exec'
            return
        self.data[arguments.name].deleted = True

    def help_delete(self):
        self.parsers.deletep.print_help()

    def do_set(self, args):
        arguments = self._parse_args(args, self.parsers.setp)
        if not arguments:                               # check for failure
            return
        if not self.data[arguments.name].deleted:  # check if deleted
            if arguments.episode:                       # rarely, if episode provided
                concerned_series = self.data[arguments.name]
                if concerned_series.has_episode(*arguments.episode):
                    concerned_series.cur_season = arguments.episode[0]
                    concerned_series.last_episode = arguments.episode[1]
                else:
                    print('\n\tEpisode '+str(arguments.episode)+' does not exist!\n')
                    self.lastcmd = 'not_exec'
                    return
            self.data['cur'] = arguments.name
        else:                                               # deleted series
            self.lastcmd = 'not_exec'
            print('\n\t' + arguments.name + ' was perviously deleted')
            print('\n\t' + 'Use "status -l" command to view all legacy Series')
            print('\n\t' + 'Use "update -a" command to add more seasons to a Series\n')


    def help_set(self):
        self.parsers.setp.print_help()

    def do_status(self, args):
        arguments = self._parse_args(args, self.parsers.statusp)
        if not arguments:           # check for failure
            return
        if arguments.name:
            if arguments.name == self.data['cur']:
                print('\n\t\t:: *' + arguments.name +'* ::\n')
            else:
                print('\n\t\t:: ' + arguments.name +' ::\n')
            print('Season Episodes')
            print('-'*75)
            # V--last_watched_Episode_for_this_series--V
            s = self.data[arguments.name].cur_season
            e = self.data[arguments.name].last_episode
            if e==0:            # if at the beginning of a season
                s -= 1
                e = self.data[arguments.name].seasons[s-1]
            for season, episodes in \
                        enumerate(self.data[arguments.name].seasons, start=1):
                episodes_repr = '+' * episodes
                episodes_repr += str(episodes)
                if season is s:
                    episodes_repr = episodes_repr[:e-1] + '@' + episodes_repr[e:]
                print(' %-6d %s' % (season, episodes_repr))
            print()
            return
        if arguments.l > 1:
            print()
            for name, series in self.data.items():
                try:
                    if series.deleted:
                        print(name)
                except AttributeError as e:     # except the 'cur' : 'SeriesN'
                    continue
            print()
            return
        if len(self.data) == 1:      # 'cur' : 'SeriesN' is always present
            print('No series in database')
            return
        else:           # 2 added to include '*' if current season is longest
            max_series_name_length = len(max(self.data.keys(), key=len)) + 2
        print()
        print(('%-' + str(max_series_name_length) + 's %s %s') % \
              ('Name', 'Seasons ', 'last_watched'))
        print('-' * 75)
        for name, series in self.data.items():
            if (name == 'cur') or (arguments.l!=1 and series.deleted):
                continue            # not asked for legacy series
            ## to set a pointer for the current series
            if name == self.data['cur']:
                name += '*'
            ## for avg_episodes_per_season
            try:
                avg_episodes_per_season = statistics.mean(series.seasons)
            except statistics.StatisticsError:
                avg_episodes_per_season = 0
            print(
                  ('%-' + str(max_series_name_length) + 's %02dx%04.1f  [%-d, %-d]') % \
                  (name, len(series.seasons), avg_episodes_per_season,\
                   series.cur_season, series.last_episode)
                  )
        print()

    def help_status(self):
        self.parsers.statusp.print_help()

    def do_update(self, args):
        arguments = self._parse_args(args, self.parsers.updatep)
        if not arguments:           # check for failure
            return
        series = self.data[arguments.name]
        if arguments.add:
            if arguments.episodes > 0:
                series.add_season(arguments.episodes)
            else:
                series.seasons.append(series.seasons[-1])
            print(('\n\tAdded season %d with episodes %d to %s') % \
                  (len(series.seasons), series.seasons[-1], series.name))
            print()
            return
        elif arguments.delete:
            if series.cur_season == len(series.seasons):
                print('\n\t Cannot delete a seoson with current episode')
                print()
                self.lastcmd = 'not_exec'
                return
            else:
                series.seasons.pop()
                print(('\n\t Deleted season %d from %s') % \
                      (len(series.seasons)+1, series.name))
                print()
            return
        elif arguments.change:
            try:
                season = int(input('Season to be changed : '))
            except ValueError as e:
                self.lastcmd = 'not_exec'
                return
            else:
                if series.has_episode(season, 0):   # check if series has the season
                    if arguments.episodes > 0:
                        if series.cur_season == season and \
                                series.last_episode > arguments.episodes:
                            print('\n\t Cannot change : current episode overflowed')
                            print()
                            self.lastcmd = 'not_exec'
                            return
                        else:
                            series.seasons[season-1] = arguments.episodes
                            print(('\n\t Season %d now has %d episodes \n') % \
                                  (season, arguments.episodes))
                    else:
                        print('\n\t Invalid argument: -e EPISODES \n')
                        self.lastcmd = 'not_exec'
                else:
                    print('\n\t Invalid Season \n')
                    self.lastcmd = 'not_exec'


    def help_update(self):
        self.parsers.updatep.print_help()


    def do_one(self, args):
        ''' move pointer by one'''
        arguments = self._parse_args(args, self.parsers.statusp)
        if not arguments:       # Check for failure
            return
        if arguments.name:
            # increase an episode for that particular series or fail
            series = self.data[arguments.name]
            if series.seasons[series.cur_season-1] == series.last_episode:
                self.lastcmd = 'not_exec'
                print('\n\tNo more episodes in this season')
                print('\n\tAdd more episodes using the "update -a" command')
                print()
                return
            else:
                series.last_episode += 1
                print(('\n\t %s last episode : [%d, %d]\n') %\
                      (series.name, series.cur_season, series.last_episode))
                return

        series = self.data[self.data['cur']]
        if series.seasons[series.cur_season-1] == series.last_episode:
            if series.next_season:
                series.cur_season = series.next_season
                series.last_episode = 0
            # V- Moving to next series -V #
            all_series = []
            for n, s in self.data.items():
                try:
                    if not s.deleted:
                        all_series.append(n)
                except AttributeError as e:         # except 'cur'; has no attr deleted
                    continue
            if len(all_series) < 2:      # if less than two undeleted series present
                print('\n\t No other Series to move to \n')
                self.lastcmd = 'not_exec'
                return
            current_series = self.data['cur']
            current_series_index = all_series.index(current_series)
            if current_series == all_series[-1]:
                current_series_index = -1
            self.data['cur'] = all_series[current_series_index+1]
            print('\n\t Moving to ' + self.data['cur'] + '\n')
            return
        series.last_episode += 1
        print(('\n\t %s last episode : [%d, %d]\n') %\
                (series.name, series.cur_season, series.last_episode))

    def do_save(self, args):
        print('Saving...')
        self._save()

    def do_exit(self, args):
        return True

if __name__ == '__main__':
    Clirials().cmdloop()
