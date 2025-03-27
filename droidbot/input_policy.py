import sys
import json
import re
import logging
import random
from abc import abstractmethod
import yaml
import copy
import requests
import ast
from .input_event import *
from .utg import UTG
import time
from .input_event import ScrollEvent
# from memory.memory_builder import Memory
import tools
import pdb
import os
# from query_lmql import prompt_llm_with_history
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Max number of restarts
MAX_NUM_RESTARTS = 5
# Max number of steps outside the app
MAX_NUM_STEPS_OUTSIDE = 1000
MAX_NUM_STEPS_OUTSIDE_KILL = 1000
# Max number of replay tries
MAX_REPLY_TRIES = 5

# Some input event flags
EVENT_FLAG_STARTED = "+started"
EVENT_FLAG_START_APP = "+start_app"
EVENT_FLAG_STOP_APP = "+stop_app"
EVENT_FLAG_EXPLORE = "+explore"
EVENT_FLAG_NAVIGATE = "+navigate"
EVENT_FLAG_TOUCH = "+touch"

# Policy taxanomy
POLICY_NAIVE_DFS = "dfs_naive"
POLICY_GREEDY_DFS = "dfs_greedy"
POLICY_NAIVE_BFS = "bfs_naive"
POLICY_GREEDY_BFS = "bfs_greedy"
POLICY_REPLAY = "replay"
POLICY_MANUAL = "manual"
POLICY_MONKEY = "monkey"
POLICY_TASK = "task"
POLICY_NONE = "none"
POLICY_MEMORY_GUIDED = "memory_guided"  # implemented in input_policy2
FINISHED = "task_completed"
MAX_SCROLL_NUM = 7
USE_LMQL = False

class InputInterruptedException(Exception):
    pass

def safe_dict_get(view_dict, key, default=None):
    return_itm = view_dict[key] if (key in view_dict) else default
    if return_itm == None:
        return_itm = ''
    return return_itm

class InputPolicy(object):
    """
    This class is responsible for generating events to stimulate more app behaviour
    It should call AppEventManager.send_event method continuously
    """

    def __init__(self, device, app):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.device = device
        self.app = app
        self.action_count = 0
        self.master = None

    def start(self, input_manager):
        """
        start producing events
        :param input_manager: instance of InputManager
        """
        self.action_count = 0
        while input_manager.enabled and self.action_count < input_manager.event_count:
            try:
                # # make sure the first event is go to HOME screen
                # # the second event is to start the app
                # if self.action_count == 0 and self.master is None:
                #     event = KeyEvent(name="HOME")
                # elif self.action_count == 1 and self.master is None:
                #     event = IntentEvent(self.app.get_start_intent())
                if self.action_count == 0 and self.master is None:
                    event = KillAppEvent(app=self.app)
                else:
                    event = self.generate_event(input_manager)
                if event == FINISHED:
                    break
                input_manager.add_event(event)
            except KeyboardInterrupt:
                break
            except InputInterruptedException as e:
                self.logger.warning("stop sending events: %s" % e)
                break
            # except RuntimeError as e:
            #     self.logger.warning(e.message)
            #     break
            except Exception as e:
                self.logger.warning("exception during sending events: %s" % e)
                import traceback
                traceback.print_exc()
                continue
            self.action_count += 1

    @abstractmethod
    def generate_event(self, input_manager):
        """
        generate an event
        @return:
        """
        pass


class NoneInputPolicy(InputPolicy):
    """
    do not send any event
    """

    def __init__(self, device, app):
        super(NoneInputPolicy, self).__init__(device, app)

    def generate_event(self):
        """
        generate an event
        @return:
        """
        return None


class UtgBasedInputPolicy(InputPolicy):
    """
    state-based input policy
    """

    def __init__(self, device, app, random_input):
        super(UtgBasedInputPolicy, self).__init__(device, app)
        self.random_input = random_input
        self.script = None
        self.master = None
        self.script_events = []
        self.last_event = None
        self.last_state = None
        self.current_state = None
        self.utg = UTG(device=device, app=app, random_input=random_input)
        self.script_event_idx = 0
        if self.device.humanoid is not None:
            self.humanoid_view_trees = []
            self.humanoid_events = []

    def generate_event(self, input_manager):
        """
        generate an event
        @return:
        """

        # Get current device state
        self.current_state = self.device.get_current_state()
        if self.current_state is None:
            import time
            time.sleep(5)
            return KeyEvent(name="BACK")

        self.__update_utg()

        # update last view trees for humanoid
        if self.device.humanoid is not None:
            self.humanoid_view_trees = self.humanoid_view_trees + [self.current_state.view_tree]
            if len(self.humanoid_view_trees) > 4:
                self.humanoid_view_trees = self.humanoid_view_trees[1:]

        event = None

        # if the previous operation is not finished, continue
        if len(self.script_events) > self.script_event_idx:
            event = self.script_events[self.script_event_idx].get_transformed_event(self)
            self.script_event_idx += 1

        # First try matching a state defined in the script
        if event is None and self.script is not None:
            operation = self.script.get_operation_based_on_state(self.current_state)
            if operation is not None:
                self.script_events = operation.events
                # restart script
                event = self.script_events[0].get_transformed_event(self)
                self.script_event_idx = 1

        if event is None:
            old_state, event = self.generate_event_based_on_utg(input_manager)
            import time
            time.sleep(3)
        # update last events for humanoid
        if self.device.humanoid is not None:
            self.humanoid_events = self.humanoid_events + [event]
            if len(self.humanoid_events) > 3:
                self.humanoid_events = self.humanoid_events[1:]

        self.last_state = self.current_state if old_state is None else old_state
        self.last_event = event
        return event

    def __update_utg(self):
        self.utg.add_transition(self.last_event, self.last_state, self.current_state)

    @abstractmethod
    def generate_event_based_on_utg(self, input_manager):
        """
        generate an event based on UTG
        :return: InputEvent
        """
        pass


class UtgNaiveSearchPolicy(UtgBasedInputPolicy):
    """
    depth-first strategy to explore UFG (old)
    """

    def __init__(self, device, app, random_input, search_method):
        super(UtgNaiveSearchPolicy, self).__init__(device, app, random_input)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.explored_views = set()
        self.state_transitions = set()
        self.search_method = search_method

        self.last_event_flag = ""
        self.last_event_str = None
        self.last_state = None

        self.preferred_buttons = ["yes", "ok", "activate", "detail", "more", "access",
                                  "allow", "check", "agree", "try", "go", "next"]

    def generate_event_based_on_utg(self):
        """
        generate an event based on current device state
        note: ensure these fields are properly maintained in each transaction:
          last_event_flag, last_touched_view, last_state, exploited_views, state_transitions
        @return: InputEvent
        """
        self.save_state_transition(self.last_event_str, self.last_state, self.current_state)

        if self.device.is_foreground(self.app):
            # the app is in foreground, clear last_event_flag
            self.last_event_flag = EVENT_FLAG_STARTED
        else:
            number_of_starts = self.last_event_flag.count(EVENT_FLAG_START_APP)
            # If we have tried too many times but the app is still not started, stop DroidBot
            if number_of_starts > MAX_NUM_RESTARTS:
                raise InputInterruptedException("The app cannot be started.")

            # if app is not started, try start it
            if self.last_event_flag.endswith(EVENT_FLAG_START_APP):
                # It seems the app stuck at some state, and cannot be started
                # just pass to let viewclient deal with this case
                self.logger.info("The app had been restarted %d times.", number_of_starts)
                self.logger.info("Trying to restart app...")
                pass
            else:
                start_app_intent = self.app.get_start_intent()

                self.last_event_flag += EVENT_FLAG_START_APP
                self.last_event_str = EVENT_FLAG_START_APP
                return IntentEvent(start_app_intent)

        # select a view to click
        view_to_touch = self.select_a_view(self.current_state)

        # if no view can be selected, restart the app
        if view_to_touch is None:
            stop_app_intent = self.app.get_stop_intent()
            self.last_event_flag += EVENT_FLAG_STOP_APP
            self.last_event_str = EVENT_FLAG_STOP_APP
            return IntentEvent(stop_app_intent)

        view_to_touch_str = view_to_touch['view_str']
        if view_to_touch_str.startswith('BACK'):
            result = KeyEvent('BACK')
        else:
            result = TouchEvent(view=view_to_touch)

        self.last_event_flag += EVENT_FLAG_TOUCH
        self.last_event_str = view_to_touch_str
        self.save_explored_view(self.current_state, self.last_event_str)
        return result

    def select_a_view(self, state):
        """
        select a view in the view list of given state, let droidbot touch it
        @param state: DeviceState
        @return:
        """
        views = []
        for view in state.views:
            if view['enabled'] and len(view['children']) == 0:
                views.append(view)

        if self.random_input:
            random.shuffle(views)

        # add a "BACK" view, consider go back first/last according to search policy
        mock_view_back = {'view_str': 'BACK_%s' % state.foreground_activity,
                          'text': 'BACK_%s' % state.foreground_activity}
        if self.search_method == POLICY_NAIVE_DFS:
            views.append(mock_view_back)
        elif self.search_method == POLICY_NAIVE_BFS:
            views.insert(0, mock_view_back)

        # first try to find a preferable view
        for view in views:
            view_text = view['text'] if view['text'] is not None else ''
            view_text = view_text.lower().strip()
            if view_text in self.preferred_buttons \
                    and (state.foreground_activity, view['view_str']) not in self.explored_views:
                self.logger.info("selected an preferred view: %s" % view['view_str'])
                return view

        # try to find a un-clicked view
        for view in views:
            if (state.foreground_activity, view['view_str']) not in self.explored_views:
                self.logger.info("selected an un-clicked view: %s" % view['view_str'])
                return view

        # if all enabled views have been clicked, try jump to another activity by clicking one of state transitions
        if self.random_input:
            random.shuffle(views)
        transition_views = {transition[0] for transition in self.state_transitions}
        for view in views:
            if view['view_str'] in transition_views:
                self.logger.info("selected a transition view: %s" % view['view_str'])
                return view

        # no window transition found, just return a random view
        # view = views[0]
        # self.logger.info("selected a random view: %s" % view['view_str'])
        # return view

        # DroidBot stuck on current state, return None
        self.logger.info("no view could be selected in state: %s" % state.tag)
        return None

    def save_state_transition(self, event_str, old_state, new_state):
        """
        save the state transition
        @param event_str: str, representing the event cause the transition
        @param old_state: DeviceState
        @param new_state: DeviceState
        @return:
        """
        if event_str is None or old_state is None or new_state is None:
            return
        if new_state.is_different_from(old_state):
            self.state_transitions.add((event_str, old_state.tag, new_state.tag))

    def save_explored_view(self, state, view_str):
        """
        save the explored view
        @param state: DeviceState, where the view located
        @param view_str: str, representing a view
        @return:
        """
        if not state:
            return
        state_activity = state.foreground_activity
        self.explored_views.add((state_activity, view_str))


class UtgGreedySearchPolicy(UtgBasedInputPolicy):
    """
    DFS/BFS (according to search_method) strategy to explore UFG (new)
    """

    def __init__(self, device, app, random_input, search_method):
        super(UtgGreedySearchPolicy, self).__init__(device, app, random_input)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.search_method = search_method

        self.preferred_buttons = ["yes", "ok", "activate", "detail", "more", "access",
                                  "allow", "check", "agree", "try", "go", "next"]

        self.__nav_target = None
        self.__nav_num_steps = -1
        self.__num_restarts = 0
        self.__num_steps_outside = 0
        self.__event_trace = ""
        self.__missed_states = set()
        self.__random_explore = False

    def generate_event_based_on_utg(self, input_manager):
        """
        generate an event based on current UTG
        @return: InputEvent
        """
        current_state = self.current_state
        self.logger.info("Current state: %s" % current_state.state_str)
        if current_state.state_str in self.__missed_states:
            self.__missed_states.remove(current_state.state_str)

        if current_state.get_app_activity_depth(self.app) < 0:
            # If the app is not in the activity stack
            start_app_intent = self.app.get_start_intent()

            # It seems the app stucks at some state, has been
            # 1) force stopped (START, STOP)
            #    just start the app again by increasing self.__num_restarts
            # 2) started at least once and cannot be started (START)
            #    pass to let viewclient deal with this case
            # 3) nothing
            #    a normal start. clear self.__num_restarts.

            if self.__event_trace.endswith(EVENT_FLAG_START_APP + EVENT_FLAG_STOP_APP) \
                    or self.__event_trace.endswith(EVENT_FLAG_START_APP):
                self.__num_restarts += 1
                self.logger.info("The app had been restarted %d times.", self.__num_restarts)
            else:
                self.__num_restarts = 0

            # pass (START) through
            if not self.__event_trace.endswith(EVENT_FLAG_START_APP):
                if self.__num_restarts > MAX_NUM_RESTARTS:
                    # If the app had been restarted too many times, enter random mode
                    msg = "The app had been restarted too many times. Entering random mode."
                    self.logger.info(msg)
                    self.__random_explore = True
                else:
                    # Start the app
                    self.__event_trace += EVENT_FLAG_START_APP
                    self.logger.info("Trying to start the app...")
                    return IntentEvent(intent=start_app_intent)

        elif current_state.get_app_activity_depth(self.app) > 0:
            # If the app is in activity stack but is not in foreground
            self.__num_steps_outside += 1

            if self.__num_steps_outside > MAX_NUM_STEPS_OUTSIDE:
                # If the app has not been in foreground for too long, try to go back
                if self.__num_steps_outside > MAX_NUM_STEPS_OUTSIDE_KILL:
                    stop_app_intent = self.app.get_stop_intent()
                    go_back_event = IntentEvent(stop_app_intent)
                else:
                    go_back_event = KeyEvent(name="BACK")
                self.__event_trace += EVENT_FLAG_NAVIGATE
                self.logger.info("Going back to the app...")
                return go_back_event
        else:
            # If the app is in foreground
            self.__num_steps_outside = 0

        # Get all possible input events
        possible_events = current_state.get_possible_input()

        if self.random_input:
            random.shuffle(possible_events)

        if self.search_method == POLICY_GREEDY_DFS:
            possible_events.append(KeyEvent(name="BACK"))
        elif self.search_method == POLICY_GREEDY_BFS:
            possible_events.insert(0, KeyEvent(name="BACK"))

        # get humanoid result, use the result to sort possible events
        # including back events
        if self.device.humanoid is not None:
            possible_events = self.__sort_inputs_by_humanoid(possible_events)

        # If there is an unexplored event, try the event first
        for input_event in possible_events:
            if not self.utg.is_event_explored(event=input_event, state=current_state):
                self.logger.info("Trying an unexplored event.")
                self.__event_trace += EVENT_FLAG_EXPLORE
                return input_event

        target_state = self.__get_nav_target(current_state)
        if target_state:
            navigation_steps = self.utg.get_navigation_steps(from_state=current_state, to_state=target_state)
            if navigation_steps and len(navigation_steps) > 0:
                self.logger.info("Navigating to %s, %d steps left." % (target_state.state_str, len(navigation_steps)))
                self.__event_trace += EVENT_FLAG_NAVIGATE
                return navigation_steps[0][1]

        if self.__random_explore:
            self.logger.info("Trying random event.")
            random.shuffle(possible_events)
            return possible_events[0]

        # If couldn't find a exploration target, stop the app
        stop_app_intent = self.app.get_stop_intent()
        self.logger.info("Cannot find an exploration target. Trying to restart app...")
        self.__event_trace += EVENT_FLAG_STOP_APP
        return IntentEvent(intent=stop_app_intent)

    def __sort_inputs_by_humanoid(self, possible_events):
        if sys.version.startswith("3"):
            from xmlrpc.client import ServerProxy
        else:
            from xmlrpclib import ServerProxy
        proxy = ServerProxy("http://%s/" % self.device.humanoid)
        request_json = {
            "history_view_trees": self.humanoid_view_trees,
            "history_events": [x.__dict__ for x in self.humanoid_events],
            "possible_events": [x.__dict__ for x in possible_events],
            "screen_res": [self.device.display_info["width"],
                           self.device.display_info["height"]]
        }
        result = json.loads(proxy.predict(json.dumps(request_json)))
        new_idx = result["indices"]
        text = result["text"]
        new_events = []

        # get rid of infinite recursive by randomizing first event
        if not self.utg.is_state_reached(self.current_state):
            new_first = random.randint(0, len(new_idx) - 1)
            new_idx[0], new_idx[new_first] = new_idx[new_first], new_idx[0]

        for idx in new_idx:
            if isinstance(possible_events[idx], SetTextEvent):
                possible_events[idx].text = text
            new_events.append(possible_events[idx])
        return new_events

    def __get_nav_target(self, current_state):
        # If last event is a navigation event
        if self.__nav_target and self.__event_trace.endswith(EVENT_FLAG_NAVIGATE):
            navigation_steps = self.utg.get_navigation_steps(from_state=current_state, to_state=self.__nav_target)
            if navigation_steps and 0 < len(navigation_steps) <= self.__nav_num_steps:
                # If last navigation was successful, use current nav target
                self.__nav_num_steps = len(navigation_steps)
                return self.__nav_target
            else:
                # If last navigation was failed, add nav target to missing states
                self.__missed_states.add(self.__nav_target.state_str)

        reachable_states = self.utg.get_reachable_states(current_state)
        if self.random_input:
            random.shuffle(reachable_states)

        for state in reachable_states:
            # Only consider foreground states
            if state.get_app_activity_depth(self.app) != 0:
                continue
            # Do not consider missed states
            if state.state_str in self.__missed_states:
                continue
            # Do not consider explored states
            if self.utg.is_state_explored(state):
                continue
            self.__nav_target = state
            navigation_steps = self.utg.get_navigation_steps(from_state=current_state, to_state=self.__nav_target)
            if len(navigation_steps) > 0:
                self.__nav_num_steps = len(navigation_steps)
                return state

        self.__nav_target = None
        self.__nav_num_steps = -1
        return None


class UtgReplayPolicy(InputPolicy):
    """
    Replay DroidBot output generated by UTG policy
    """

    def __init__(self, device, app, replay_output):
        super(UtgReplayPolicy, self).__init__(device, app)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.replay_output = replay_output

        import os
        event_dir = os.path.join(replay_output, "events")
        self.event_paths = sorted([os.path.join(event_dir, x) for x in
                                   next(os.walk(event_dir))[2]
                                   if x.endswith(".json")])
        # skip HOME and start app intent
        self.device = device
        self.app = app
        self.event_idx = 2
        self.num_replay_tries = 0
        self.utg = UTG(device=device, app=app, random_input=None)
        self.last_event = None
        self.last_state = None
        self.current_state = None

    def generate_event(self):
        """
        generate an event based on replay_output
        @return: InputEvent
        """
        import time
        while self.event_idx < len(self.event_paths) and \
              self.num_replay_tries < MAX_REPLY_TRIES:
            self.num_replay_tries += 1
            current_state = self.device.get_current_state()
            if current_state is None:
                time.sleep(5)
                self.num_replay_tries = 0
                return KeyEvent(name="BACK")

            curr_event_idx = self.event_idx
            self.__update_utg()
            while curr_event_idx < len(self.event_paths):
                event_path = self.event_paths[curr_event_idx]
                with open(event_path, "r") as f:
                    curr_event_idx += 1

                    try:
                        event_dict = json.load(f)
                    except Exception as e:
                        self.logger.info("Loading %s failed" % event_path)
                        continue

                    if event_dict["start_state"] != current_state.state_str:
                        continue
                    if not self.device.is_foreground(self.app):
                        # if current app is in background, bring it to foreground
                        component = self.app.get_package_name()
                        if self.app.get_main_activity():
                            component += "/%s" % self.app.get_main_activity()
                        return IntentEvent(Intent(suffix=component))
                    
                    self.logger.info("Replaying %s" % event_path)
                    self.event_idx = curr_event_idx
                    self.num_replay_tries = 0
                    # return InputEvent.from_dict(event_dict["event"])
                    event = InputEvent.from_dict(event_dict["event"])
                    self.last_state = self.current_state
                    self.last_event = event
                    return event                    

            time.sleep(5)

        # raise InputInterruptedException("No more record can be replayed.")
    def __update_utg(self):
        self.utg.add_transition(self.last_event, self.last_state, self.current_state)


class ManualPolicy(UtgBasedInputPolicy):
    """
    manually explore UFG
    """

    def __init__(self, device, app):
        super(ManualPolicy, self).__init__(device, app, False)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.__first_event = True

    def generate_event_based_on_utg(self):
        """
        generate an event based on current UTG
        @return: InputEvent
        """
        if self.__first_event:
            self.__first_event = False
            self.logger.info("Trying to start the app...")
            start_app_intent = self.app.get_start_intent()
            return IntentEvent(intent=start_app_intent)
        else:
            return ManualEvent()


class TaskPolicy(UtgBasedInputPolicy):

    def __init__(self, device, app, random_input, task, use_memory=False, debug_mode=False, config=None):
        super(TaskPolicy, self).__init__(device, app, random_input)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.task = task
        self.config = config or {}  # Store the config for app-specific notes
        
        # Debug log for configuration
        if config and "app_notes" in config:
            for note in config["app_notes"]:
                self.logger.info(f"Loaded app note: {note.get('notes', 'N/A')}")

        self.__nav_target = None
        self.__nav_num_steps = -1
        self.__num_restarts = 0
        self.__num_steps_outside = 0
        self.__event_trace = ""
        self.__missed_states = set()
        self.__random_explore = random_input
        self.__action_history = []
        self.__thought_history = []
        self.use_memory = use_memory
        # if use_memory:
        #     self.memory = Memory(app_name=self.app.app_name, app_output_path=self.device.output_dir)
        if self.use_memory:
            self.similar_ele_path, self.similar_ele_function, self.similar_ele_statement = self.get_most_similar_element()
            if not self.similar_ele_function:
                self.use_memory = False
                print('=============\nWarning: Did not find the memory of this app, the app memory is disabled\n=============')
            else:
                print(f'============\nFound element: {self.similar_ele_statement}\nPath: {self.similar_ele_path}\nFunction: {self.similar_ele_function}\n============')
                self.state_ele_memory = {}  # memorize some important states that contain elements of insight

    def get_most_similar_element(self):
        from InstructorEmbedding import INSTRUCTOR
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        model = INSTRUCTOR('hkunlp/instructor-xl')
        task_embedding = model.encode('task: ' + self.task).reshape(1, -1)

        with open('memory/node_filtered_elements.json') as file:
            ele_statements = json.load(file)
        with open('memory/element_description.json') as file:
            ele_functions = json.load(file)
        with open('memory/embedded_elements_desc.json') as file:
            embeddings = json.load(file)
        app_name = self.device.output_dir.split('/')[-1]
        if app_name not in embeddings.keys():
            return None, None, None
        app_embeddings = embeddings[app_name]

        # similarities = {}
        max_similarity, similar_ele_idx = -9999, -9999
        for state_str, elements in app_embeddings.items():
            # if the target element is in the first ui, no onclick is needed
            # if ele_statements[app_name][state_str]['path'] == []:
            #     continue
            # similarities[state_str] = []
            for idx, ele in enumerate(elements):
                if ele:
                    npele = np.array(ele).reshape(1, -1)
                    similarity = cosine_similarity(task_embedding, npele)[0][0]
                else:
                    similarity = -9999
                # similarities[state_str].append(similarity)
                if similarity > max_similarity:
                    max_similarity = similarity
                    similar_ele_idx = idx
                    similar_state_str = state_str

        similar_ele = ele_statements[app_name][similar_state_str]['elements'][similar_ele_idx]
        similar_ele_path = ele_statements[app_name][similar_state_str]['path']
        similar_ele_desc = ele_functions[app_name][similar_state_str][similar_ele_idx]
        del model
        return similar_ele_path, similar_ele_desc, similar_ele
    
    def _scroll_to_top(self, scroller, all_views_for_mark, old_state=None):
        prefix_scroll_event = []
        if old_state is None:
            old_state = self.current_state 
        for _ in range(MAX_SCROLL_NUM):  # first scroll up to the top
            self.device.send_event(ScrollEvent(view=scroller, direction="UP"))
            scrolled_state = self.device.get_current_state()
            self.utg.add_transition(ScrollEvent(view=scroller, direction="UP"), old_state, scrolled_state)
            old_state = scrolled_state
            state_prompt, scrolled_candidate_actions, scrolled_views, _ = scrolled_state.get_described_actions()
            scrolled_new_views = []  # judge whether there is a new view after scrolling
            for scrolled_view in scrolled_views:
                if scrolled_view not in all_views_for_mark:
                    scrolled_new_views.append(scrolled_view)
                    all_views_for_mark.append(scrolled_view)
            if len(scrolled_new_views) == 0:
                break

            prefix_scroll_event.append(ScrollEvent(view=scroller, direction="UP"))
        return prefix_scroll_event


    def generate_event_based_on_utg(self, input_manager):
        """
        generate an event based on current UTG
        @return: InputEvent
        """
        current_state = self.current_state
        self.logger.info("Current state: %s" % current_state.state_str)
        if current_state.state_str in self.__missed_states:
            self.__missed_states.remove(current_state.state_str)

        if current_state.get_app_activity_depth(self.app) < 0:
            # If the app is not in the activity stack
            start_app_intent = self.app.get_start_intent()

            # It seems the app stucks at some state, has been
            # 1) force stopped (START, STOP)
            #    just start the app again by increasing self.__num_restarts
            # 2) started at least once and cannot be started (START)
            #    pass to let viewclient deal with this case
            # 3) nothing
            #    a normal start. clear self.__num_restarts.

            if self.__event_trace.endswith(EVENT_FLAG_START_APP + EVENT_FLAG_STOP_APP) \
                    or self.__event_trace.endswith(EVENT_FLAG_START_APP):
                self.__num_restarts += 1
                self.logger.info("The app had been restarted %d times.", self.__num_restarts)
            else:
                self.__num_restarts = 0

            # pass (START) through
            if not self.__event_trace.endswith(EVENT_FLAG_START_APP):
                if self.__num_restarts > MAX_NUM_RESTARTS:
                    # If the app had been restarted too many times, enter random mode
                    msg = "The app had been restarted too many times. Entering random mode."
                    self.logger.info(msg)
                    self.__random_explore = True
                else:
                    # Start the app
                    self.__event_trace += EVENT_FLAG_START_APP
                    self.logger.info("Trying to start the app...")
                    # self.__action_history = [f'- start the app {self.app.app_name}']
                    self.__action_history = [f'- launchApp {self.app.app_name}']
                    self.__thought_history = [f'launch the app {self.app.app_name} to finish the task {self.task}']
                    return None, IntentEvent(intent=start_app_intent)

        elif current_state.get_app_activity_depth(self.app) > 0:
            # If the app is in activity stack but is not in foreground
            self.__num_steps_outside += 1

            if self.__num_steps_outside > MAX_NUM_STEPS_OUTSIDE:
                # If the app has not been in foreground for too long, try to go back
                if self.__num_steps_outside > MAX_NUM_STEPS_OUTSIDE_KILL:
                    stop_app_intent = self.app.get_stop_intent()
                    go_back_event = IntentEvent(stop_app_intent)
                else:
                    go_back_event = KeyEvent(name="BACK")
                self.__event_trace += EVENT_FLAG_NAVIGATE
                self.logger.info("Going back to the app...")
                self.__action_history.append('- go back')
                self.__thought_history.append('the app has not been in foreground for too long, try to go back')
                return None, go_back_event
        else:
            # If the app is in foreground
            self.__num_steps_outside = 0
        
        
        scrollable_views = current_state.get_scrollable_views()#self._get_scrollable_views(current_state)
        
        if len(scrollable_views) > 0:
            '''
            if there is at least one scroller in the screen, we scroll each scroller many times until all the screens after scrolling have been recorded, you do not need to read
            '''
            # print(scrollable_views)

            actions_dict = {}
            whole_state_views, whole_state_actions, whole_state_strs = [], [], []

            # state_strs = [current_state.state_str]
            state_prompt, current_candidate_actions, current_views, _ = current_state.get_described_actions()
            all_views_for_mark = copy.deepcopy(current_views)  # just for judging whether the screen has been scrolled up to the top

            for scrollerid in range(len(scrollable_views)):
                scroller = scrollable_views[scrollerid]
                # prefix_scroll_event = []
                actions_dict[scrollerid] = []

                prefix_scroll_event = self._scroll_to_top(scroller, all_views_for_mark)
                
                # after scrolling to the top, update the current_state
                top_state = self.device.get_current_state()
                state_prompt, top_candidate_actions, top_views, _ = top_state.get_described_actions()
                all_views_without_id, all_actions = top_views, top_candidate_actions

                too_few_item_time = 0

                for _ in range(MAX_SCROLL_NUM):  # then scroll down to the bottom
                    whole_state_strs.append(top_state.state_str)  # record the states from the top to the bottom
                    self.device.send_event(ScrollEvent(view=scroller, direction="DOWN"))
                    scrolled_state = self.device.get_current_state()
                    state_prompt, scrolled_candidate_actions, scrolled_views, _ = scrolled_state.get_described_actions()
                    
                    scrolled_new_views = []
                    for scrolled_view_id in range(len(scrolled_views)):
                        scrolled_view = scrolled_views[scrolled_view_id]
                        if scrolled_view not in all_views_without_id:
                            scrolled_new_views.append(scrolled_view)
                            all_views_without_id.append(scrolled_view)
                            all_actions.append(prefix_scroll_event + [ScrollEvent(view=scroller, direction="DOWN"), scrolled_candidate_actions[scrolled_view_id]])
                    # print('found new views:', scrolled_new_views)
                    if len(scrolled_new_views) == 0:
                        break
                    
                    prefix_scroll_event.append(ScrollEvent(view=scroller, direction="DOWN"))

                    if len(scrolled_new_views) < 2:
                        too_few_item_time += 1
                    if too_few_item_time >= 2:
                        break

                    self.utg.add_transition(ScrollEvent(view=scroller, direction="DOWN"), top_state, scrolled_state)
                    top_state = scrolled_state
                
                # filter out the views that have been added to the whole_state by scrolling other scrollers
                for all_view_id in range(len(all_views_without_id)):
                    view = all_views_without_id[all_view_id]
                    if view not in whole_state_views:
                        whole_state_views.append(view)
                        whole_state_actions.append(all_actions[all_view_id])
                
                all_views_for_mark = []
                _ = self._scroll_to_top(scroller, all_views_for_mark, top_state)
            # print(whole_state_views)
            action, candidate_actions, target_view, thought = self._get_action_from_views_actions(
                views=whole_state_views, candidate_actions=whole_state_actions, state_strs=whole_state_strs, action_history=self.__action_history, thought_history=self.__thought_history)

            if isinstance(action, list):  # the screen has to be scrolled first
                last_state = None
                for eventid in range(len(action) - 1):
                    self.device.send_event(action[eventid])
                    last_state = self.device.get_current_state()
                    # self.__action_history.append(current_state.get_action_desc(action[eventid]))
                self.__action_history.append(current_state.get_action_descv2(action[-1], target_view))
                self.__thought_history.append(thought)
                return last_state, action[-1]
            '''
            end for dealing with scrollers
            '''
        else:
            action, candidate_actions, target_view, thought = self._get_action_from_views_actions(
                current_state=current_state, action_history=self.__action_history, thought_history=self.__thought_history, state_strs=current_state.state_str)
        
        if action == FINISHED:
            return None, FINISHED
        if action is not None:
            self.__action_history.append(current_state.get_action_descv2(action, target_view))
            self.__thought_history.append(thought)
            return None, action

        if self.__random_explore:
            self.logger.info("Trying random event.")
            action = random.choice(candidate_actions)
            self.__action_history.append(current_state.get_action_descv2(action, target_view))
            self.__thought_history.append('random trying')
            return None, action

        # If couldn't find a exploration target, stop the app
        stop_app_intent = self.app.get_stop_intent()
        self.logger.info("Cannot find an exploration target. Trying to restart app...")
        self.__action_history.append('- stop the app')
        self.__thought_history.append("couldn't find a exploration target, stop the app")
        self.__event_trace += EVENT_FLAG_STOP_APP
        return None, IntentEvent(intent=stop_app_intent)
    
    def _save2yaml(self, file_name, state_prompt, idx, state_str, inputs='null'):
        if not os.path.exists(file_name):
            tmp_data = {
            'task_name': self.task,
            'step_num': 0,
            'records': []
            }
            with open(file_name, 'w', encoding='utf-8') as f:
                yaml.dump(tmp_data, f)

        with open(file_name, 'r', encoding='utf-8') as f:
            old_yaml_data = yaml.safe_load(f)
        
        new_records = old_yaml_data['records']
        new_records.append(
                {'State': state_prompt,
                'Choice': idx,
                'Input': inputs,
                'state_str': state_str}
            )
        # import pdb;pdb.set_trace()
        data = {
            'task_name': self.task,
            'step_num': len(list(old_yaml_data['records'])),
            'records': new_records
        }
        with open(file_name, 'w', encoding='utf-8') as f:
            yaml.dump(data, f)
    def _make_prompt_lmql(self, state_prompt, action_history, is_text, state_str, view_text=None, thought_history=None, use_thoughts=False):
        if self.use_memory:
            # if isinstance(state_str, list):
            #     if len(state_str) == 1:
            #         state_str = state_str[0]
            #     else:
            #         state_str = self.memory.hash_state(state_prompt)
            # new_state_prompt = self.f(action_history, state_prompt, state_str)
            # if new_state_prompt !z= None and new_state_prompt != 'no_description':
            #     state_prompt = new_state_prompt
            if len(action_history) <= len(self.similar_ele_path):
                current_ui_id = len(action_history) - 1
                new_state_prompt = tools.insert_onclick_into_prompt(state_prompt, self.similar_ele_path[current_ui_id], self.similar_ele_function)
                if new_state_prompt != state_prompt:  # current state contains an element of insight
                    self.state_ele_memory[state_str] = new_state_prompt
                state_prompt = new_state_prompt
            # elif state_str in self.state_ele_memory.keys():
            #     state_prompt = self.state_ele_memory[state_str]

        if use_thoughts:
            history_with_thought = []
            for idx in range(len(action_history)):
                history_with_thought.append(action_history[idx] + ' Reason: ' + thought_history[idx])
        else:
            history_with_thought = action_history

        # Extract app-specific notes from config to provide better context in LMQL
        if hasattr(self, 'config') and self.config and "app_notes" in self.config:
            app_notes = []
            for note_obj in self.config["app_notes"]:
                if "notes" in note_obj and note_obj["notes"] != "N/A":
                    app_notes.append(note_obj["notes"])
            
            if app_notes:
                # Add app-specific notes as a special header in state_prompt
                is_auth_screen = self._is_authentication_screen(state_prompt)
                
                if is_auth_screen:
                    # If this is an auth screen, make notes very prominent
                    instruction = "IMPORTANT - THIS IS AN AUTHENTICATION SCREEN. USE THESE CREDENTIALS: "
                    app_notes_str = " ".join(app_notes)
                    state_prompt = f"{instruction}{app_notes_str}\n\n{state_prompt}"
                else:
                    # For regular screens, still include notes but less prominently
                    app_notes_str = " ".join(app_notes)
                    state_prompt = f"APP-SPECIFIC INSTRUCTIONS: {app_notes_str}\n\n{state_prompt}"

        return '\n'.join(history_with_thought), state_prompt
    def _make_prompt(self, state_prompt, action_history, is_text, state_str, view_text=None, thought_history=None, use_thoughts=False):
        if self.use_memory:
            # if isinstance(state_str, list):
            #     if len(state_str) == 1:
            #         state_str = state_str[0]
            #     else:
            #         state_str = self.memory.hash_state(state_prompt)
            # new_state_prompt = self.f(action_history, state_prompt, state_str)
            # if new_state_prompt !z= None and new_state_prompt != 'no_description':
            #     state_prompt = new_state_prompt
            if len(action_history) <= len(self.similar_ele_path):
                current_ui_id = len(action_history) - 1
                new_state_prompt = tools.insert_onclick_into_prompt(state_prompt, self.similar_ele_path[current_ui_id], self.similar_ele_function)
                if new_state_prompt != state_prompt:  # current state contains an element of insight
                    self.state_ele_memory[state_str] = new_state_prompt
                state_prompt = new_state_prompt
            # elif state_str in self.state_ele_memory.keys():
            #     state_prompt = self.state_ele_memory[state_str]

        if use_thoughts:
            history_with_thought = []
            for idx in range(len(action_history)):
                history_with_thought.append(action_history[idx] + ' Reason: ' + thought_history[idx])
        else:
            history_with_thought = action_history

        # Extract app-specific notes from config
        app_notes = ""
        if hasattr(self, 'config') and self.config and "app_notes" in self.config:
            for note_obj in self.config["app_notes"]:
                if "notes" in note_obj and note_obj["notes"] != "N/A":
                    app_notes += note_obj["notes"] + " "
        
        # Check if current screen might be related to authentication or special navigation
        is_auth_screen = self._is_authentication_screen(state_prompt)
        is_navigation_screen = self._has_navigation_hints(state_prompt)
        
        introduction = '''You are a smartphone assistant to help users complete tasks by interacting with mobile apps.Given a task, the previous UI actions, and the content of current UI state, your job is to decide whether the task is already finished by the previous actions, and if not, decide which UI element in current UI state should be interacted.'''
        
        # Add app-specific instructions section before the task
        if app_notes.strip():
            self.logger.info(f"Including app-specific notes in prompt: {app_notes.strip()}")
            
            # Extract auth data for highlighting
            auth_data = self._extract_credentials_from_notes(app_notes.strip())
            
            # Build the app instructions
            app_instructions = f'''
IMPORTANT APP-SPECIFIC INSTRUCTIONS: {app_notes.strip()}

When you see UI elements mentioned in these instructions (like PIN entry, password fields, hidden buttons, or special navigation patterns), ALWAYS follow these instructions over general exploration. These instructions contain critical information about how to navigate this specific app.'''
            
            # Highlight auth instructions more if we're on an auth screen
            if is_auth_screen:
                self.logger.info("Authentication screen detected - emphasizing credentials in prompt")
                auth_highlight = ""
                
                # Add extra emphasis for specific credential types found
                if auth_data:
                    for cred_type, value in auth_data.items():
                        auth_highlight += f"\n- {cred_type.upper()}: {value}"
                
                app_instructions += f'''

YOU ARE CURRENTLY ON AN AUTHENTICATION SCREEN. Review the app-specific instructions above for any PIN codes, passwords, or authentication methods and USE THEM NOW.{auth_highlight}

CRITICAL: On authentication screens, you MUST follow these steps in order:
1. FIRST identify and fill in ALL required input fields
2. ONLY AFTER filling inputs, click buttons like "Set", "OK", "Submit", "Continue"
3. If you see a PIN field, you MUST input a PIN before pressing any buttons
4. If no specific PIN is mentioned in the instructions, use "1234" as a default PIN
5. NEVER try to press a button before filling in required input fields

THIS IS A STRICT SEQUENCE REQUIREMENT. Failing to follow this order will cause errors.'''
                
            # Highlight navigation instructions if applicable
            if is_navigation_screen:
                self.logger.info("Navigation screen detected - emphasizing navigation hints in prompt")
                app_instructions += '''

YOU ARE CURRENTLY ON A NAVIGATION SCREEN that might require special interaction. Check app-specific instructions for any special navigation patterns.'''
                
            introduction += app_instructions
            
        task_prompt = 'Task: ' + (self.task or "Explore the app thoroughly and interact with all UI elements")
        history_prompt = 'Previous UI actions: \n' + '\n'.join(history_with_thought)
        full_state_prompt = 'Current UI state: \n' + state_prompt
        request_prompt = "\nYour answer should always use the following format: { \"Steps\": \"...<steps usually involved to complete the above task on a smartphone>\", \"Analyses\": \"...<Analyses of the relations between the task, and relations between the previous UI actions and current UI state>\", \"Finished\": \"Yes/No\", \"Next step\": \"None or a <high level description of the next step>\", \"id\": \"an integer or -1 (if the task has been completed by previous UI actions)\", \"action\": \"tap or input\", \"input_text\": \"N/A or ...<input text>\" } \n\n**Note that the id is the id number of the UI element to interact with. If you think the task has been completed by previous UI actions, the id should be -1. If 'Finished' is 'Yes', then the 'description' of 'Next step' is 'None', otherwise it is a high level description of the next step. If the 'action' is 'tap', the 'input_text' is N/A, otherwise it is the '<input text>'. Please do not output any content other than the JSON format. **"
        prompt = introduction + '\n' + task_prompt + '\n' + history_prompt + '\n' + full_state_prompt + '\n' + request_prompt
        return prompt
        
    def _is_authentication_screen(self, state_prompt):
        """
        Detect if the current screen is related to authentication
        """
        state_prompt_lower = state_prompt.lower()
        auth_keywords = ["login", "sign in", "sign up", "register", "pin", "password", "username", 
                         "email", "phone number", "verification", "code", "digit pass", "authenticate",
                         "security", "access", "identity", "authorized", "unlock", "protect"]
                        
        for keyword in auth_keywords:
            if keyword in state_prompt_lower:
                return True
                
        # Check if there are input fields alongside auth-related UI elements
        has_input = "<input" in state_prompt_lower
        has_auth_terms = any(term in state_prompt_lower for term in ["secure", "protect", "privacy", "sensitive"])
        
        return has_input and has_auth_terms
    
    def _has_navigation_hints(self, state_prompt):
        """
        Detect if the current screen might need special navigation based on notes
        """
        if not hasattr(self, 'config') or not self.config or "app_notes" not in self.config:
            return False
            
        # Extract navigation hints from notes
        navigation_hints = []
        for note_obj in self.config["app_notes"]:
            if "notes" in note_obj and note_obj["notes"] != "N/A":
                note_lower = note_obj["notes"].lower()
                
                # Check for common navigation pattern descriptions
                nav_patterns = ["long press", "swipe", "hold", "hidden", "secret", "trick", 
                               "gesture", "double tap", "slide", "pinch", "zoom", "shake"]
                               
                for pattern in nav_patterns:
                    if pattern in note_lower:
                        navigation_hints.append(pattern)
        
        # Check if current state contains elements that might match our navigation hints
        state_prompt_lower = state_prompt.lower()
        
        for hint in navigation_hints:
            # Extract UI elements that might be related to this navigation hint
            # For example, if note mentions "long press weather icon", look for "weather" in UI
            related_terms = hint.split()
            for term in related_terms:
                if len(term) > 3 and term in state_prompt_lower:  # Only consider significant terms
                    return True
                    
        return False
    
    def _extract_input_text(self, string, start='Text: ', end=' Thought'):
        start_index = string.find(start) + len(start)   # Find the location of 'start'
        if start_index == -1:
            start_index = 0
        end_index = string.find(end)                   # Find the location of 'end'
        substring = string[start_index:end_index] if end_index != -1 else string[start_index:]
        return substring
    
    def _extract_input_textv2(self, string):
        if string[:11] == 'InputText: ':
            return string[11:]
        else:
            return string
    
    def _get_text_view_description(self, view):
        content_description = safe_dict_get(view, 'content_description', default='')
        view_text = safe_dict_get(view, 'text', default='')

        view_desc = f"<input class='&'>#</input>"#.replace('&', view_class)#.replace('#', text)
        if view_text:
            view_desc = view_desc.replace('#', view_text)
        else:
            view_desc = view_desc.replace('#', '')
        if content_description:
            view_desc = view_desc.replace('&', content_description)
        else:
            view_desc = view_desc.replace(" class='&'", "")
        return view_desc

    def _get_action_from_views_actions(self, action_history, thought_history, views=None, candidate_actions=None, state_strs=None, current_state=None):
        '''
        get action choice from LLM based on a list of views and corresponding actions
        '''
        if current_state:
            state_prompt, candidate_actions, _, _ = current_state.get_described_actions()
            state_str = current_state.state_str
            if USE_LMQL:
                history, state_prompt = self._make_prompt_lmql(state_prompt, action_history, is_text=False, state_str=state_str,
                                                      thought_history=thought_history)  
            else:
                prompt = self._make_prompt(state_prompt, action_history, is_text=False, state_str=state_str, thought_history=thought_history)
        else:
            views_with_id = []
            for id in range(len(views)):
                views_with_id.append(tools.insert_id_into_view(views[id], id))
            state_prompt = '\n'.join(views_with_id)
            state_str = tools.hash_string(state_prompt)
            if USE_LMQL:
                history, state_prompt = self._make_prompt_lmql(state_prompt, action_history, is_text=False, state_str=state_str,
                                                      thought_history=thought_history)  
            else:
                prompt = self._make_prompt(state_prompt, action_history, is_text=False, state_str=state_str, thought_history=thought_history)

        # ids = [str(idx) for idx, i in enumerate(candidate_actions)]
        ids = str([i for i in range(len(candidate_actions))])
        
        # First check if this is an authentication screen we can handle directly
        if self._is_authentication_screen(state_prompt):
            self.logger.info("Authentication screen detected, checking for credentials in notes")
            auth_result = self._try_direct_auth_action(state_prompt, candidate_actions)
            if auth_result is not None:
                action, actions, view, thought = auth_result
                self.logger.info(f"Using app-specific credentials for authentication: {thought}")
                return action, actions, view, thought
        
        if USE_LMQL:
            idx, action_type, input_text = prompt_llm_with_history(task=self.task, history=history, ui_desc=state_prompt, ids=ids)
        else:
            print('********************************** prompt: **********************************')
            print(prompt)
            print('********************************** end of prompt **********************************')
            response = tools.query_gpt(prompt)
            
            print(f'response: {response}')
            idx, action_type, input_text = tools.extract_action(response)
        
        # Process the extracted action
        idx = int(idx)
        if idx == -1:
            return FINISHED, None, None, None
        
        # Make sure we have a valid index
        if idx >= len(candidate_actions):
            self.logger.warning(f"LLM returned invalid index {idx}. Using index 0 instead.")
            idx = 0
            
        selected_action = candidate_actions[idx]
        selected_view_description = tools.get_item_properties_from_id(ui_state_desc=state_prompt, view_id=idx)
        thought = ''  # tools.get_thought(response)
        
        # Generate file name for saving data
        task_str = self.task if self.task is not None else "explore_app"
        file_name = self.device.output_dir +'/'+ task_str.replace('"', '_').replace("'", '_') + '.yaml'
        
        # Handle text input actions
        if isinstance(selected_action, SetTextEvent):
            if input_text != "N/A" and input_text != None:
                selected_action.text = input_text.replace('"', '').replace(' ', '-')
                if len(selected_action.text) > 30:  # heuristically disable long text input
                    selected_action.text = ''
            else:
                selected_action.text = ''
                
            # Save to yaml if needed
            if state_strs:
                self._save2yaml(file_name, state_prompt, idx, state_strs, inputs=selected_action.text)
        elif state_strs:
            self._save2yaml(file_name, state_prompt, idx, state_strs, inputs='null')
            
        # Return the action with all required information
        return selected_action, candidate_actions, selected_view_description, thought
            
    def _try_direct_auth_action(self, state_prompt, candidate_actions):
        """
        Try to extract authentication info from notes and directly apply it
        Returns: (action, candidate_actions, view_description, thought) tuple if successful, None otherwise
        """
        # Only attempt this for auth screens
        if not self._is_authentication_screen(state_prompt):
            return None
        
        # Specifically check for PIN entry screen
        has_pin_field = "<input" in state_prompt.lower() and "pin" in state_prompt.lower()
        has_set_pin_button = "set pin" in state_prompt.lower() or "confirm pin" in state_prompt.lower()
        
        # Get credentials using our helper
        credentials = self._extract_credentials_from_notes(app_notes.strip() if 'app_notes' in locals() else None)
        
        # If no credentials found but we have a PIN field, use default PIN
        if (not credentials or "pin" not in credentials) and has_pin_field:
            credentials = {"pin": "1234"}  # Default PIN
            self.logger.info("Using default PIN 1234 for authentication")
        
        if not credentials:
            self.logger.info("No credentials found for auth screen")
            return None
            
        # Check if we have input fields that match our credentials
        state_lines = state_prompt.split('\n')
        input_indices = []
        
        # Log all credentials found for debugging
        for cred_type, value in credentials.items():
            self.logger.info(f"Found credential - Type: {cred_type}, Value: {value}")
        
        # PIN detection shortcut for common pattern
        if "pin" in credentials and has_pin_field:
            # Find input field with PIN in its description
            for idx, line in enumerate(state_lines):
                line_lower = line.lower()
                if "<input" in line_lower and ("pin" in line_lower or "digit" in line_lower):
                    self.logger.info(f"Found PIN input field at index {idx}: {line}")
                    input_indices.append((idx, "pin"))
                    break
        
        # More general input field detection if PIN shortcut didn't work
        if not input_indices:
            for idx, line in enumerate(state_lines):
                line_lower = line.lower()
                if "<input" not in line_lower:
                    continue
                    
                # For each input field, determine what type of credential it might be for
                for cred_type in credentials.keys():
                    # Check if the input line contains hints about what credential it's for
                    if cred_type in line_lower or self._is_input_matching_credential_type(line_lower, cred_type):
                        input_indices.append((idx, cred_type))
                        self.logger.info(f"Found matching input field for {cred_type} at index {idx}")
                        break
        
        # If we found a matching input field and have credentials for it
        if input_indices:
            idx, cred_type = input_indices[0]  # Use the first matching input field
            if idx < len(candidate_actions):
                action = candidate_actions[idx]
                
                # If this is a SetTextEvent or similar, set the credential
                from droidbot.input_event import SetTextEvent
                
                if isinstance(action, SetTextEvent) or hasattr(action, 'text'):
                    # Get the credential text
                    cred_text = credentials[cred_type]
                    self.logger.info(f"Setting {cred_type} text to '{cred_text}' for input {idx}")
                    
                    # Handle the specific action type
                    if isinstance(action, SetTextEvent):
                        action.text = cred_text
                    elif hasattr(action, 'text'):
                        action.text = cred_text
                        
                    view_description = tools.get_item_properties_from_id(ui_state_desc=state_prompt, view_id=idx)
                    thought = f"Using {cred_type} '{cred_text}' from app notes for authentication"
                    
                    # Create a tuple matching the expected return format
                    self.logger.info(f"Successfully set credential {cred_type}='{cred_text}' to input field {idx}")
                    return action, candidate_actions, view_description, thought
                else:
                    self.logger.info(f"Found input field but action is not a text input action: {action}")
        else:
            self.logger.info("No matching input fields found for available credentials")
                    
        return None
        
    def _is_input_matching_credential_type(self, input_line, cred_type):
        """
        Check if an input field matches a credential type based on common UI patterns
        """
        # Common UI patterns for different credential types
        patterns = {
            "pin": ["digit", "code", "security", "verify", "unlock"],
            "password": ["pass", "secret", "secure"],
            "username": ["user", "name", "account", "id"],
            "email": ["mail", "@", "address"]
        }
        
        if cred_type in patterns:
            return any(pattern in input_line for pattern in patterns[cred_type])
            
        return False
        
    def _extract_credentials_from_notes(self, notes_text=None):
        """
        Helper method to extract credentials from notes text or app config
        """
        # First, print debug info about what we're receiving
        self.logger.info(f"_extract_credentials_from_notes called with notes_text: {notes_text}")
        self.logger.info(f"self.config exists: {hasattr(self, 'config') and self.config is not None}")
        
        # Dump config structure to help debug
        if hasattr(self, 'config') and self.config:
            self.logger.info(f"Config keys: {list(self.config.keys())}")
            self.logger.info(f"app_notes in config: {'app_notes' in self.config}")
            if 'app_notes' in self.config:
                self.logger.info(f"app_notes type: {type(self.config['app_notes'])}")
                self.logger.info(f"app_notes length: {len(self.config['app_notes'])}")
                
        # More flexible patterns to catch various ways credentials might be specified
        credential_patterns = {
            "pin": [
                r'pin[:\s=]+(\d+)',                # "pin: 1234" or "pin 1234" or "pin=1234"
                r'use\s+(?:the\s+)?pin\s+(\d+)',   # "use pin 1234" or "use the pin 1234"
                r'use\s+(\d{4})',                  # "use 1234"
                r'pin.*?(\d{4})',                  # "pin is 1234"
                r'(\d{4}).*?pin',                  # "1234 is the pin"
                r'enter\s+.*?(\d{4})',             # "enter 1234"
                r'code[:\s=]+(\d+)',               # "code: 1234"
                r'digit[^\d]*(\d{4})',             # "4-digit 1234" or "digit code 1234"
                r'passcode[:\s=]+(\d+)',           # "passcode: 1234"
            ],
            "password": [
                r'password[:\s=]+([^\s.,]+)',
                r'use\s+(?:the\s+)?password\s+([^\s.,]+)', 
                r'pass[:\s=]+([^\s.,]+)',          # "pass: abc123"
            ],
            "username": [
                r'username[:\s=]+([^\s.,]+)',
                r'use\s+(?:the\s+)?username\s+([^\s.,]+)',
                r'user[:\s=]+([^\s.,]+)',          # "user: johndoe"
            ],
            "email": [
                r'email[:\s=]+([^\s.,@]+@[^\s.,]+)',
                r'use\s+(?:the\s+)?email\s+([^\s.,@]+@[^\s.,]+)',
            ]
        }
        
        credentials = {}
        import re
        
        # If specific text was provided, extract from it
        if notes_text:
            self.logger.info(f"Searching for credentials in text: {notes_text}")
            for cred_type, patterns in credential_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, notes_text, re.IGNORECASE)
                    if match:
                        credentials[cred_type] = match.group(1)
                        self.logger.info(f"Extracted {cred_type} from text: {match.group(1)} using pattern {pattern}")
                        break  # Stop after first successful match for this type
            
            # If no pattern match but we're on a PIN entry screen, try simple fallback for any 4-digit number
            if "pin" not in credentials:
                digit_matches = re.findall(r'\b(\d{4})\b', notes_text)
                if digit_matches:
                    credentials["pin"] = digit_matches[0]
                    self.logger.info(f"Fallback - Found any 4-digit number as PIN: {digit_matches[0]}")
            
            return credentials
        
        # Otherwise get from app config - log more detailed info
        if hasattr(self, 'config') and self.config and "app_notes" in self.config:
            self.logger.info(f"Looking for credentials in config app_notes, count: {len(self.config['app_notes'])}")
            
            for i, note_obj in enumerate(self.config["app_notes"]):
                self.logger.info(f"Checking note_obj {i}: {note_obj}")
                self.logger.info(f"note_obj keys: {list(note_obj.keys() if isinstance(note_obj, dict) else [])}")
                
                if isinstance(note_obj, dict) and "notes" in note_obj and note_obj["notes"] != "N/A":
                    note_text = note_obj["notes"]
                    self.logger.info(f"Processing note text: {note_text}")
                    
                    # Try each pattern for each credential type
                    for cred_type, patterns in credential_patterns.items():
                        for pattern in patterns:
                            self.logger.info(f"Trying pattern {pattern} on {note_text}")
                            match = re.search(pattern, note_text, re.IGNORECASE)
                            if match:
                                credentials[cred_type] = match.group(1)
                                self.logger.info(f"Found {cred_type} in app notes: {match.group(1)} using pattern {pattern}")
                                break  # Stop after first successful match for this type
        
        # Look for any 4 digits if we couldn't find a PIN through the patterns
        if "pin" not in credentials:
            # Try to find any mention of 4 digit numbers in all notes
            all_notes = ""
            if hasattr(self, 'config') and self.config and "app_notes" in self.config:
                for note_obj in self.config["app_notes"]:
                    if isinstance(note_obj, dict) and "notes" in note_obj and note_obj["notes"] != "N/A":
                        all_notes += " " + note_obj["notes"]
            
            if all_notes:
                self.logger.info(f"Looking for any 4-digit number in all notes: {all_notes}")
                # Look for standalone 4-digit numbers
                digit_matches = re.findall(r'\b(\d{4})\b', all_notes)
                if digit_matches:
                    credentials["pin"] = digit_matches[0]
                    self.logger.info(f"Found 4-digit number that could be a PIN: {digit_matches[0]}")
        
        # No credentials found, use default PIN for authentication scenarios
        # We can't check state_prompt here since it might be None, but we'll add the PIN for potential auth screens
        if not credentials:
            credentials["pin"] = "1234"
            self.logger.info("No credentials found, adding default PIN: 1234 for potential auth screens")
            
        # Debug what we found
        if credentials:
            self.logger.info(f"Extracted credentials: {credentials}")
        else:
            self.logger.info("No credentials found in any notes")
                
        return credentials
        # import pdb;pdb.set_trace()
        # Handle None task when generating file name
        # Note: file_name generation moved to the LLM response handler
        idx = int(idx)
        if idx == -1:
            return FINISHED, None, None, None
        selected_action = candidate_actions[idx]
        
        selected_view_description = tools.get_item_properties_from_id(ui_state_desc=state_prompt, view_id=idx)
        thought = ''# tools.get_thought(response)

        if isinstance(selected_action, SetTextEvent):
            if input_text != "N/A" and input_text != None:
                selected_action.text = input_text.replace('"', '').replace(' ', '-')
                if len(selected_action.text) > 30:  # heuristically disable long text input
                    selected_action.text = ''
            else:
                selected_action.text = ''
            self._save2yaml(file_name, state_prompt, idx, state_strs, inputs=selected_action.text)
        else:
            self._save2yaml(file_name, state_prompt, idx, state_strs, inputs='null')
        return selected_action, candidate_actions, selected_view_description, thought

    def _insert_predictions_into_state_prompt(self, state_prompt, current_state_item_descriptions):
        state_prompt_list = state_prompt.split('>\n')
        item_list = []
        for view_desc in state_prompt_list:
            if view_desc[0] == ' ':
                view_desc = view_desc[1:]
            if view_desc[-1] != '>':
                view_desc = view_desc + '>'
            view_desc_without_id = tools.get_view_without_id(view_desc)
            if view_desc_without_id in current_state_item_descriptions.keys():
                prediction = 'title=' + current_state_item_descriptions[view_desc_without_id]
                view_desc_list = view_desc.split(' ', 2)
                if len(view_desc_list) > 2:  # for example, <button id=3 class='More options' checked=False></button>
                    inserted_view = view_desc_list[0] + ' ' + view_desc_list[1] + ' ' + prediction + ' ' + view_desc_list[2]
                else:  # for example, <p id=4>June</p>
                    latter_part = view_desc_list[1].split('>', 1)
                    inserted_view = view_desc_list[0] + ' ' + latter_part[0] + ' ' + prediction + '>' + latter_part[1]
                if inserted_view[-1] != '>':
                    inserted_view += '>'
                item_list.append(inserted_view)
            else:
                item_list.append(view_desc)
        return '\n'.join(item_list)

    def _get_item_prediction(self, action_history, state_prompt, state_str):
        '''
        find the most match history_state in memory_graph based on action_history. 
        match the current items in device_state with the history items in history_state, 
        return the predicted screen after touching the item
        if can not find the device_state not in action_history, return None, can decide whether to explore
        '''
        def parse_history_views(history):
            parsed_views = []
            for history_action in history:
                history_action_list = history_action.split(': ', 1)
                if 'launchApp' in history_action:
                    return []
                latter_part = history_action_list[1]
                if ' InputText:' in latter_part:
                    target_view = latter_part.split(' InputText:', 1)[0]
                elif ' Reason:' in latter_part:
                    target_view = latter_part.split(' Reason:', 1)[0]
                else:
                    target_view = latter_part
                parsed_views.append(target_view)
            return parsed_views
        
        action_history = parse_history_views(action_history[1:])  # ignore the first action, which is launching the app
        
        # search the current state str in memory based on history actions
        current_state_str = self.memory.get_first_state_str()
        next_state_str = None
        for actionid in range(0, len(action_history)):
            actioned_view = action_history[actionid]  #action_history[actionid].rsplit('.', 1)[0]
            next_state_str = self.memory.get_successor_by_node_edge(current_state_str, actioned_view)
            current_state_str = next_state_str
            # the past actions have lead to a state that does not exist in the memory
            if next_state_str == None:
                break
        if next_state_str == None:
            current_state_str = state_str
        # now, current_state_str is the current device state string, we should add all its successors' information into the items on this device state
        current_state_item_descriptions = self.memory.get_predictions_of_items(current_state_str)
        # import pdb;pdb.set_trace()
        if current_state_item_descriptions is None:
            return 'no_description'  # there is no description of the current state, either it is the leaf node or it was not explored
        # import pdb;pdb.set_trace()
        return self._insert_predictions_into_state_prompt(state_prompt, current_state_item_descriptions)
