# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
import ryu.ofproto.ofproto_v1_3 as ofp
import ryu.ofproto.ofproto_v1_3_parser as ofparser
import ryu.ofproto.openstate_v1_0 as osp
import ryu.ofproto.openstate_v1_0_parser as osparser
from ryu.lib import hub
from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.node import UserSwitch,RemoteController
import os,subprocess,time,sys
from ryu.ofproto.ofproto_common import OPENSTATE_EXPERIMENTER_ID

class OpenStateErrorExperimenterMsg(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(OpenStateErrorExperimenterMsg, self).__init__(*args, **kwargs)
        if os.geteuid() != 0:
            exit("You need to have root privileges to run this script")
        # Kill Mininet
        os.system("sudo mn -c 2> /dev/null")
        print 'Starting Mininet'
        self.net = Mininet(topo=SingleSwitchTopo(7),switch=UserSwitch,controller=RemoteController,cleanup=True,autoSetMacs=True,listenPort=6634,autoStaticArp=True)
        self.net.start()
        self.last_error_queue = []
        self.test_id = 0

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.monitor_thread = hub.spawn(getattr(self, '_monitor%s' % self.test_id),datapath)
        self.test_id += 1

    def add_flow(self, datapath, priority, match, actions):

        inst = [ofparser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = ofparser.OFPFlowMod(
                datapath=datapath, cookie=0, cookie_mask=0, table_id=0,
                command=ofp.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
                priority=priority, buffer_id=ofp.OFP_NO_BUFFER,
                out_port=ofp.OFPP_ANY,
                out_group=ofp.OFPG_ANY,
                flags=0, match=match, instructions=inst)
        datapath.send_msg(mod)

    def send_table_mod(self, datapath):
        req = osparser.OFPExpMsgConfigureStatefulTable(datapath=datapath, table_id=0, stateful=1)
        datapath.send_msg(req)

    def send_key_lookup(self, datapath):
        key_lookup_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_L_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC,ofp.OXM_OF_ETH_DST], table_id=0)
        datapath.send_msg(key_lookup_extractor)

    def send_key_update(self, datapath):
        key_update_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_U_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC,ofp.OXM_OF_ETH_DST], table_id=0)
        datapath.send_msg(key_update_extractor)

    def test0(self,datapath):
        self.send_key_lookup(datapath)
        self.send_key_update(datapath)
        

    def test1(self,datapath):
        self.send_table_mod(datapath)
        self.send_key_lookup(datapath)
        self.send_key_update(datapath)
        actions = [ofparser.OFPActionOutput(2,0)]
        match = ofparser.OFPMatch(in_port=1,state=6)
        self.add_flow(datapath, 150, match, actions)

        actions = [osparser.OFPExpActionSetState(state=6,table_id=10)]
        match = ofparser.OFPMatch(in_port=1)
        self.add_flow(datapath, 100, match, actions)

        actions = [ofparser.OFPActionOutput(1,0)]
        match = ofparser.OFPMatch(in_port=2)
        self.add_flow(datapath, 200, match, actions)

    def test2(self,datapath):
        self.send_table_mod(datapath)
        self.send_key_lookup(datapath)
        self.send_key_update(datapath)
        actions = [ofparser.OFPActionOutput(2,0)]
        match = ofparser.OFPMatch(in_port=1,state=6)
        self.add_flow(datapath, 150, match, actions)

        actions = [osparser.OFPExpActionSetState(state=6,table_id=200)]
        match = ofparser.OFPMatch(in_port=1)
        self.add_flow(datapath, 100, match, actions)

        actions = [ofparser.OFPActionOutput(1,0)]
        match = ofparser.OFPMatch(in_port=2)
        self.add_flow(datapath, 200, match, actions)

    def test3(self,datapath):
        self.send_table_mod(datapath)

        # I provide zero fields => I cannot set an empty extractor!
        key_lookup_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_L_EXTRACTOR, fields=[], table_id=0)
        datapath.send_msg(key_lookup_extractor)
        # I provide more fields than allowed
        key_lookup_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_L_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC,ofp.OXM_OF_ETH_DST,ofp.OXM_OF_IPV4_DST,ofp.OXM_OF_TCP_SRC,ofp.OXM_OF_TCP_DST,ofp.OXM_OF_UDP_SRC,ofp.OXM_OF_UDP_DST], table_id=0)
        datapath.send_msg(key_lookup_extractor)

    def test4(self,datapath):
        self.send_table_mod(datapath)
        self.send_key_lookup(datapath)
        self.send_key_update(datapath)
        # I provide zero keys => I cannot access the state table with an empty key!
        state = osparser.OFPExpMsgSetFlowState(datapath=datapath, state=88, keys=[], table_id=0)
        datapath.send_msg(state)
        # I provide more keys than allowed
        state = osparser.OFPExpMsgSetFlowState(datapath=datapath, state=88, keys=[0,0,0,0,0,2,0,0,0,0,0,4,0,0,0,0,0,2,0,0,0,0,0,4,0,0,0,0,0,2,0,0,0,0,0,4,0,0,0,0,0,2,0,0,0,0,0,4,5], table_id=0)
        datapath.send_msg(state)

    def test5(self,datapath):
        self.send_table_mod(datapath)
        key_lookup_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_L_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC], table_id=0)
        datapath.send_msg(key_lookup_extractor)
        key_update_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_U_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC], table_id=0)
        datapath.send_msg(key_update_extractor)
        state = osparser.OFPExpMsgSetFlowState(datapath=datapath, state=88, keys=[10,0,0,5], table_id=0)
        datapath.send_msg(state)

    def test6(self,datapath):
        self.send_table_mod(datapath)
        key_lookup_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_L_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC], table_id=0)
        datapath.send_msg(key_lookup_extractor)
        key_update_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_U_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC], table_id=0)
        datapath.send_msg(key_update_extractor)
        state = osparser.OFPExpMsgDelFlowState(datapath=datapath, keys=[10,0,0,5], table_id=0)
        datapath.send_msg(state)

    def test7(self,datapath):
        self.send_table_mod(datapath)
        key_lookup_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_L_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC,ofp.OXM_OF_ETH_DST], table_id=0)
        datapath.send_msg(key_lookup_extractor)
        key_update_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_U_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC], table_id=0)
        datapath.send_msg(key_update_extractor)

    def test8(self,datapath):
        self.send_table_mod(datapath)
        key_update_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_U_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC], table_id=0)
        datapath.send_msg(key_update_extractor)
        key_lookup_extractor = osparser.OFPExpMsgKeyExtract(datapath=datapath, command=osp.OFPSC_EXP_SET_L_EXTRACTOR, fields=[ofp.OXM_OF_ETH_SRC,ofp.OXM_OF_ETH_DST], table_id=0)
        datapath.send_msg(key_lookup_extractor)

    def test9(self,datapath):
        self.send_table_mod(datapath)
        self.send_key_lookup(datapath)
        self.send_key_update(datapath)
        state = osparser.OFPExpMsgSetFlowState(datapath=datapath, state=88, keys=[0,0,0,0,0,2,0,0,0,0,0,4], table_id=200)
        datapath.send_msg(state)

    def test10(self,datapath):
        self.send_table_mod(datapath)
        actions = [ofparser.OFPActionOutput(6,0)]
        match = ofparser.OFPMatch(in_port=5,ip_proto=1,eth_type=0x800,global_state=2863311530)
        self.add_flow(datapath, 150, match, actions)

        msg = osparser.OFPExpSetGlobalState(datapath=datapath, global_state=2863311530, global_state_mask=0xffffffff)
        datapath.send_msg(msg)

        actions = [ofparser.OFPActionOutput(5,0)]
        match = ofparser.OFPMatch(in_port=6,ip_proto=1,eth_type=0x800)
        self.add_flow(datapath, 150, match, actions)

    def test11(self,datapath):
        self.send_table_mod(datapath)
        (global_state, global_state_mask) = osparser.masked_global_state_from_str("1*1*1*1*1*1*1*1*0*0*1*1*1*1*1*1*")
        actions = [ofparser.OFPActionOutput(6,0)]
        match = ofparser.OFPMatch(in_port=5,eth_type=0x800,ip_proto=1,global_state=osparser.masked_global_state_from_str("1*1*1*1*1*1*1*1*0*0*1*1*1*1*1*1*"))
        self.add_flow(datapath, 150, match, actions)

        msg = osparser.OFPExpSetGlobalState(datapath=datapath, global_state=global_state, global_state_mask=global_state_mask)
        datapath.send_msg(msg)

        actions = [ofparser.OFPActionOutput(5,0)]
        match = ofparser.OFPMatch(in_port=6,ip_proto=1,eth_type=0x800)
        self.add_flow(datapath, 200, match, actions)

    def test12(self,datapath):
        self.send_table_mod(datapath)
        actions = [ofparser.OFPActionOutput(6,0)]
        match = ofparser.OFPMatch(in_port=5,ip_proto=1,eth_type=0x800,global_state=1492)
        self.add_flow(datapath, 200, match, actions)

        actions = [osparser.OFPExpActionSetGlobalState(global_state=1492)]
        match = ofparser.OFPMatch(in_port=5,eth_type=0x800,ip_proto=1)
        self.add_flow(datapath, 100, match, actions)

        actions = [ofparser.OFPActionOutput(5,0)]
        match = ofparser.OFPMatch(in_port=6,eth_type=0x800,ip_proto=1)
        self.add_flow(datapath, 200, match, actions)

    def test13(self,datapath):
        self.send_table_mod(datapath)
        (global_state, global_state_mask) = osparser.masked_global_state_from_str("*1*1*1*1*0*0*1*1*1*1*1*1*")
        actions = [ofparser.OFPActionOutput(6,0)]
        match = ofparser.OFPMatch(in_port=5,eth_type=0x800,ip_proto=1,global_state=osparser.masked_global_state_from_str("*1*1*1*1*0*0*1*1*1*1*1*1*"))
        self.add_flow(datapath, 200, match, actions)

        actions = [osparser.OFPExpActionSetGlobalState(global_state=global_state, global_state_mask=global_state_mask)]
        match = ofparser.OFPMatch(in_port=5,eth_type=0x800,ip_proto=1)
        self.add_flow(datapath, 100, match, actions)

        actions = [ofparser.OFPActionOutput(5,0)]
        match = ofparser.OFPMatch(in_port=6,eth_type=0x800,ip_proto=1)
        self.add_flow(datapath, 200, match, actions)

    def _monitor0(self,datapath):
        print("Network is ready")

        # [TEST 0] Setting the extractor on a stateless stage should be impossible
        self.test0(datapath)

        attempts = 0
        while len(self.last_error_queue)!=2 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==2 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_EXP_SET_EXTRACTOR) and self.last_error_queue[1]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_EXP_SET_EXTRACTOR):
            print 'Test 0: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 0: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor1(self,datapath):
        print("Network is ready")

        # [TEST 1] Set state action must be performed onto a stateful stage (run-time check => no error is returned!)
        # mininet> h1 ping -c5 h2
        # ping should fail, but rules are correctly installed
        self.test1(datapath)
        
        attempts = 0
        while len(self.last_error_queue)==0 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        drop_perc = self.net.ping(hosts=[self.net.hosts[0],self.net.hosts[1]],timeout=1)
        if len(self.last_error_queue)==0 and drop_perc == 100.0:
            print 'Test 1: \x1b[32mSUCCESS!\x1b[0m'
        else:
            print 'Test 1: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor2(self,datapath):
        print("Network is ready")

        # [TEST 2] Set state action must be performed onto a stage with table_id less or equal than the number of pipeline's tables (install-time check)
        self.test2(datapath)

        attempts = 0
        while len(self.last_error_queue)!=1 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==1 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_TABLE_ID):
            print 'Test 2: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 2: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()
        
    def _monitor3(self,datapath):
        print("Network is ready")

        # [TEST 3]  OFPExpMsgKeyExtract: I should provide a number of fields >0 and <MAX_FIELD_COUNT
        self.test3(datapath)

        attempts = 0
        while len(self.last_error_queue)!=2 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==2 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_EXP_LEN) and self.last_error_queue[1]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_EXP_LEN):
            print 'Test 3: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 3: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor4(self,datapath):
        print("Network is ready")

        # [TEST 4] OFPExpMsgSetFlowState: I should provide a key of size >0 and <MAX_KEY_LEN
        self.test4(datapath)

        attempts = 0
        while len(self.last_error_queue)!=2 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==2 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_EXP_LEN) and self.last_error_queue[1]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_EXP_LEN):
            print 'Test 4: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 4: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor5(self,datapath):
        print("Network is ready")

        # [TEST 5] OFPExpMsgSetFlowState: I should provide a key of size consistent with the number of fields of the update-scope
        self.test5(datapath)

        attempts = 0
        while len(self.last_error_queue)!=1 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==1 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_EXP_LEN):
            print 'Test 5: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 5: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor6(self,datapath):
        print("Network is ready")

        # [TEST 6] OFPExpMsgDelFlowState: I should provide a key of size consistent with the number of fields of the update-scope
        self.test6(datapath)

        attempts = 0
        while len(self.last_error_queue)!=1 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==1 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_EXP_LEN):
            print 'Test 6: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 6: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor7(self,datapath):
        print("Network is ready")

        # [TEST 7] OFPExpMsgKeyExtract: lookup-scope and update-scope must provide same length keys
        self.test7(datapath)

        attempts = 0
        while len(self.last_error_queue)!=1 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==1 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_EXP_LEN):
            print 'Test 7: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 7: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor8(self,datapath):
        print("Network is ready")

        # [TEST 8] OFPExpMsgKeyExtract: lookup-scope and update-scope must provide same length keys
        self.test8(datapath)

        attempts = 0
        while len(self.last_error_queue)!=1 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==1 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_EXP_LEN):
            print 'Test 8: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 8: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor9(self,datapath):
        print("Network is ready")

        # [TEST 9] OFPExpMsgSetFlowState: must be executed onto a stage with table_id<=64 (number of pipeline's tables)
        self.test9(datapath)

        attempts = 0
        while len(self.last_error_queue)!=1 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        if len(self.last_error_queue)==1 and self.last_error_queue[0]==(ofp.OFPET_EXPERIMENTER,osp.OFPEC_BAD_TABLE_ID):
            print 'Test 9: \x1b[32mSUCCESS!\x1b[0m'
            self.last_error_queue = []
        else:
            print 'Test 9: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor10(self,datapath):
        print("Network is ready")

        # [TEST 10] exact match on global_state
        # mininet> h5 ping -c1 h6
        self.test10(datapath)
        
        attempts = 0
        while len(self.last_error_queue)==0 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        drop_perc = self.net.ping(hosts=[self.net.hosts[4],self.net.hosts[5]],timeout=1)
        if len(self.last_error_queue)==0 and drop_perc == 0.0:
            print 'Test 10: \x1b[32mSUCCESS!\x1b[0m'
        else:
            print 'Test 10: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor11(self,datapath):
        print("Network is ready")

        # [TEST 11] masked match on global_state
        # mininet> h5 ping -c1 h6
        self.test11(datapath)
        
        attempts = 0
        while len(self.last_error_queue)==0 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        drop_perc = self.net.ping(hosts=[self.net.hosts[4],self.net.hosts[5]],timeout=1)
        if len(self.last_error_queue)==0 and drop_perc == 0.0:
            print 'Test 11: \x1b[32mSUCCESS!\x1b[0m'
        else:
            print 'Test 11: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor12(self,datapath):
        print("Network is ready")

        # [TEST 12] exact match on global_state
        # mininet> h5 ping -c2 h6
        # the first ping should fail
        self.test12(datapath)
        
        attempts = 0
        while len(self.last_error_queue)==0 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        # TODO: if Mininet had 'count' parameter we could simplify the code by checking drop_perc=0.25 with count=2

        drop_perc = self.net.ping(hosts=[self.net.hosts[4],self.net.hosts[5]],timeout=1)
        if len(self.last_error_queue)!=0 or drop_perc != 50.0:
            print 'Test 12: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        drop_perc = self.net.ping(hosts=[self.net.hosts[4],self.net.hosts[5]],timeout=1)
        if len(self.last_error_queue)==0 and drop_perc == 0.0:
            print 'Test 12: \x1b[32mSUCCESS!\x1b[0m'
        else:
            print 'Test 12: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        self.restart_mininet()

    def _monitor13(self,datapath):
        print("Network is ready")

        # [TEST 13] masked match on global_state
        # mininet> h5 ping -c5 h6
        # the first ping should fail
        self.test12(datapath)
        
        attempts = 0
        while len(self.last_error_queue)==0 and attempts<3:
            print 'Waiting %d seconds...' % (3-attempts)
            attempts += 1
            time.sleep(1)

        # TODO: if Mininet had 'count' parameter we could simplify the code by checking drop_perc=0.25 with count=2

        drop_perc = self.net.ping(hosts=[self.net.hosts[4],self.net.hosts[5]],timeout=1)
        if len(self.last_error_queue)!=0 or drop_perc != 50.0:
            print 'Test 13: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        drop_perc = self.net.ping(hosts=[self.net.hosts[4],self.net.hosts[5]],timeout=1)
        if len(self.last_error_queue)==0 and drop_perc == 0.0:
            print 'Test 13: \x1b[32mSUCCESS!\x1b[0m'
        else:
            print 'Test 13: \x1b[31mFAIL\x1b[0m'
            self.stop_test_and_exit()

        #self.restart_mininet()
        self.stop_test_and_gracefully_exit()

    @set_ev_cls(ofp_event.EventOFPErrorExperimenterMsg,
                    [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def exp_error_msg_handler(self, ev):
        msg = ev.msg
        if msg.experimenter == OPENSTATE_EXPERIMENTER_ID:
            self.last_error_queue.append((msg.type,msg.exp_type))

    def stop_test_and_exit(self):
        # Kill Mininet and/or Ryu
        self.net.stop()
        os.system("sudo mn -c 2> /dev/null")
        os.system("kill -9 $(pidof -x ryu-manager) 2> /dev/null")

    def stop_test_and_gracefully_exit(self):
        # Kill Mininet and/or Ryu
        self.net.stop()
        os.system("sudo mn -c 2> /dev/null")
        # Send SIGTERM instead of SIGKILL
        os.system("kill -7 $(pidof -x ryu-manager) 2> /dev/null")

    def restart_mininet(self):
        print 'Restarting Mininet\n'
        os.system("sudo mn -c 2> /dev/null")
        self.net = Mininet(topo=SingleSwitchTopo(7),switch=UserSwitch,controller=RemoteController,cleanup=True,autoSetMacs=True,listenPort=6634,autoStaticArp=True)
        self.net.start()