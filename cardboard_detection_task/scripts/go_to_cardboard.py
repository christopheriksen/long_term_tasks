#!/usr/bin/env python

import os
import subprocess
import rospy
import actionlib
from actionlib_msgs.msg import GoalStatus
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from fetch_auto_dock_msgs.msg import DockAction, DockGoal, UndockAction, UndockGoal

import smach
import smach_ros

tag_1_goal = MoveBaseGoal()
tag_1_goal.target_pose.header.frame_id = "map"
tag_1_goal.target_pose.pose.position.x = -14.6
tag_1_goal.target_pose.pose.position.y = 3.2199
tag_1_goal.target_pose.pose.orientation.z = -0.731
tag_1_goal.target_pose.pose.orientation.w = 0.6825

tag_2_goal = MoveBaseGoal()
tag_2_goal.target_pose.header.frame_id = "map"
tag_2_goal.target_pose.pose.position.x = -0.076
tag_2_goal.target_pose.pose.position.y = 4.738
tag_2_goal.target_pose.pose.orientation.z = -0.735
tag_2_goal.target_pose.pose.orientation.w = 0.6778

dock_goal = MoveBaseGoal()
dock_goal.target_pose.header.frame_id = "map"
dock_goal.target_pose.pose.position.x = -1.053
dock_goal.target_pose.pose.position.y = -0.123
dock_goal.target_pose.pose.orientation.z = 0.055
dock_goal.target_pose.pose.orientation.w = 0.998

goals = [tag_1_goal, tag_2_goal, dock_goal]


def print_status(status):
    g_status = GoalStatus()

    if status == g_status.PREEMPTED:
        print("PREEMPTED")
    elif status == g_status.ABORTED:
        print("ABORTED")
    elif status == g_status.REJECTED:
        print("REJECTED")
    elif status == g_status.SUCCEEDED:
        print("SUCCEEDED")


@smach.cb_interface(input_keys=['counter'], output_keys=['counter'], outcomes=['succeeded'])
def cardboard_imaging_cb(ud):
    p = subprocess.Popen([os.path.expanduser('~/long_term_ws/devel/env.sh'), 'roslaunch', 'cardboard_detection_task', 'cardboard_capture_{}.launch'.format(ud.counter+1)])
    while p.poll() is None: # wait until launchfile exits
        pass
    ud.counter += 1
    p = subprocess.Popen([os.path.expanduser('~/long_term_ws/devel/env.sh'), 'roslaunch', 'cardboard_detection_task', 'detect_cardboard.launch'])
    while p.poll() is None: # wait until launchfile exits
        pass
    return 'succeeded'

def get_smach_sm():
    sm = smach.StateMachine(outcomes=['succeeded', 'aborted', 'preempted'])
    sm.userdata.counter = 0

    with sm:
        smach.StateMachine.add('UNDOCK',
                               smach_ros.SimpleActionState('undock', UndockAction, goal=UndockGoal(rotate_in_place=True)),
                               {'aborted':'GO_TO_CARDBOARD_1'}) # Why does this action always abort when it works every time???

        smach.StateMachine.add('GO_TO_CARDBOARD_1',
                               smach_ros.SimpleActionState('move_base', MoveBaseAction, goal=tag_1_goal),
                               {'succeeded':'TAKE_IMAGE_1',
                                'aborted':'GO_TO_DOCK'})

        smach.StateMachine.add('TAKE_IMAGE_1',
                               smach.CBState(cardboard_imaging_cb),
                               {'succeeded':'GO_TO_CARDBOARD_2'})

        smach.StateMachine.add('GO_TO_CARDBOARD_2',
                               smach_ros.SimpleActionState('move_base', MoveBaseAction, goal=tag_2_goal),
                               {'succeeded':'TAKE_IMAGE_2',
                                'aborted':'GO_TO_DOCK'})

        smach.StateMachine.add('TAKE_IMAGE_2',
                               smach.CBState(cardboard_imaging_cb),
                               {'succeeded':'GO_TO_DOCK'})

        smach.StateMachine.add('GO_TO_DOCK',
                               smach_ros.SimpleActionState('move_base', MoveBaseAction, goal=dock_goal),
                               {'succeeded':'DOCK'})

        smach.StateMachine.add('DOCK',
                               smach_ros.SimpleActionState('dock', DockAction),
                               {'succeeded':'succeeded'})

    return sm

def movebase_client():
    dock_client = actionlib.SimpleActionClient('dock', DockAction)
    dock_client.wait_for_server()

    undock_client = actionlib.SimpleActionClient('undock', UndockAction)
    undock_client.wait_for_server()

    client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
    client.wait_for_server()

    u_goal = UndockGoal()
    u_goal.rotate_in_place = True
    undock_client.send_goal(u_goal)
    undock_client.wait_for_result()
    print(undock_client.get_result())
    print_status(undock_client.get_state())

    for i, goal in enumerate(goals):
        client.send_goal(goal)
        wait = client.wait_for_result()
        print("Client Goal:")
        print(client.get_result())
        print_status(client.get_state())
        print("Should have printed")
        if not wait:
            rospy.logger("Action server not available!")
            rospy.signal_shutdown("Action server not available!")
            break
        if i == 0 or i == 1: # stupid hacky thing
            # Do Chris's CV thing here
            p = subprocess.Popen([os.path.expanduser('~/long_term_ws/devel/env.sh'), 'roslaunch', 'cardboard_detection_task', 'cardboard_capture_{}.launch'.format(i+1)])
            while p.poll() is None: # wait until launchfile exits
                pass
            p = subprocess.Popen([os.path.expanduser('~/long_term_ws/devel/env.sh'), 'roslaunch', 'cardboard_detection_task', 'detect_cardboard.launch'])
            while p.poll() is None: # wait until launchfile exits
                pass
        elif i == 2:
            dock_client.send_goal(DockGoal())
            dock_client.wait_for_result()
            print(dock_client.get_result())
            print_status(dock_client.get_state())

if __name__ == '__main__':
    try:
        rospy.init_node('movebase_client_py')
        sm = get_smach_sm()
        sm.execute()
        '''
        result = movebase_client()
        if result:
            rospy.loginfo("Goal execution done!")
        '''
    except rospy.ROSInterruptException:
        rospy.logwarn("Interrupt!")

