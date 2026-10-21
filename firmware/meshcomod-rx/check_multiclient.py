#!/usr/bin/env python3
"""Compile exact production routing/history methods with hardware I/O doubles.

This proves source behavior, not ESP32 sockets, Wi-Fi coexistence or live HACS.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(sys.argv[1]).resolve()
mesh=(root/'examples/companion_radio/MyMesh.cpp').read_text()
router=(root/'src/helpers/esp32/MultiTransportCompanionInterface.cpp').read_text()
def method(source,signature):
    start=source.index(signature);end=source.index('\n}',start)+2
    return source[start:end]+'\n'
code=r'''
#include <cassert>
#include <cstring>
#include <cstdint>
#include <vector>
#include <iostream>
#include "examples/companion_radio/LoRagotchiRX.h"
#define MAX_FRAME_SIZE 176
#define HISTORY_RING_SIZE 128
#define MAX_HISTORY_CLIENTS 8
#define MAX_CLIENT_ID_LEN 31
#define RESP_CODE_CONTACT_MSG_RECV 7
#define RESP_CODE_CHANNEL_MSG_RECV 8
#define RESP_CODE_CONTACT_MSG_RECV_V3 16
#define RESP_CODE_CHANNEL_MSG_RECV_V3 17
#define REPLY_TARGET_USB -1
#define REPLY_TARGET_BLE -2
#define REPLY_TARGET_WS_0 100
#define WS_COMPANION_MAX_CLIENTS 2
#define TCP_COMPANION_MAX_CLIENTS 3
struct Port {
 std::vector<int> recipients;
 size_t writeFrame(const uint8_t*,size_t n){recipients.push_back(-1);return n;}
 size_t writeToClient(int c,const uint8_t*,size_t n){recipients.push_back(c);return n;}
};
struct MultiTransportCompanionInterface {
 Port _usb,_tcp,_ws;
 bool _tcp_started=true,_ws_started=true;
 int _last_reply_target=-1;
 static const size_t _max_client_id_len=32;
 char _client_ids[7][32]={};
 size_t writeFrame(const uint8_t[],size_t);
 int _clientIdSlot() const;
 void setCurrentClientId(const char*);
 void getCurrentClientId(char*,size_t) const;
};
struct MyMesh {
 struct HistoryEntry{uint8_t len;uint8_t buf[MAX_FRAME_SIZE];uint32_t seq;};
 struct ClientHistoryState{char client_id[32];uint32_t last_delivered_seq;};
 HistoryEntry history_ring[128]={};
 int history_count=0,history_head=0;
 uint32_t history_next_seq=1;
 ClientHistoryState history_clients[8]={};
 int history_num_clients=0;
 uint32_t addToHistoryRing(const uint8_t[],int);
 int getNextFromHistoryForClient(const char*,uint8_t[],uint32_t*,bool);
 void commitHistoryForClient(const char*,uint32_t);
};
'''
for sig in ('size_t MultiTransportCompanionInterface::writeFrame(', 'int MultiTransportCompanionInterface::_clientIdSlot(', 'void MultiTransportCompanionInterface::setCurrentClientId(', 'void MultiTransportCompanionInterface::getCurrentClientId('):code+=method(router,sig)
for sig in ('static bool clientIdEqual(', 'uint32_t MyMesh::addToHistoryRing(', 'int MyMesh::getNextFromHistoryForClient(', 'void MyMesh::commitHistoryForClient('):code+=method(mesh,sig)
code+=r'''
struct IO:lrx::IO {
 bool save(const lrx::Journal&)override{return true;}
 bool send(const uint8_t*,const char*,uint32_t&,uint32_t&)override{return true;}
};
int main(){
 MultiTransportCompanionInterface mux;uint8_t payload[]={0x70,'R','X',1,0,1};
 for(int dest:{-1,0,1,2,100,101}){
  mux._last_reply_target=dest;assert(mux.writeFrame(payload,6)==6);
 }
 assert((mux._usb.recipients==std::vector<int>{-1}));
 assert((mux._tcp.recipients==std::vector<int>{0,1,2}));
 assert((mux._ws.recipients==std::vector<int>{0,1}));
 char id[32];mux._last_reply_target=1;mux.setCurrentClientId("aq-stable");
 mux._last_reply_target=0;mux.getCurrentClientId(id,32);assert(!strcmp(id,"tcp0"));
 mux._last_reply_target=1;mux.getCurrentClientId(id,32);assert(!strcmp(id,"aq-stable"));
 mux.setCurrentClientId(nullptr);mux.getCurrentClientId(id,32);assert(!strcmp(id,"tcp1"));
 mux._last_reply_target=2;mux.setCurrentClientId("aq-stable");
 mux.getCurrentClientId(id,32);assert(!strcmp(id,"aq-stable"));
 std::cout<<"PASS production command replies target USB/TCP/WS origin only; client ID survives slot change\n";
 MyMesh history;uint8_t first[]={17,1},second[]={17,2},out[176];uint32_t seq=0;
 history.addToHistoryRing(first,2);history.addToHistoryRing(second,2);
 for(auto client:{"tcp0","aq-stable"}){
  assert(history.getNextFromHistoryForClient(client,out,&seq,false)==2 && out[1]==1);
  assert(history.getNextFromHistoryForClient(client,out,&seq,false)==2 && out[1]==1); // failed write: no cursor advance
  history.commitHistoryForClient(client,seq);
  assert(history.getNextFromHistoryForClient(client,out,&seq,false)==2 && out[1]==2);
  history.commitHistoryForClient(client,seq);
  assert(history.getNextFromHistoryForClient(client,out,&seq,false)==0);
 }
 std::cout<<"PASS production history: both clients receive oldest/newest independently; failed write replays\n";
 IO io;lrx::Receiver rx(io);rx.begin(nullptr,0);uint8_t command[]={0x70,'R','X',1,0,1,0,0,0},identity[32]={3};
 assert(rx.command(command,9,out,1,identity,7)==10 && out[5]==0);
 command[5]=2;assert(rx.command(command,9,out,2,identity,7)==6 && out[5]==2);
 assert(rx.command(command,9,out,16001,identity,7)==10 && out[5]==0);
 std::cout<<"PASS production RX lease rejects second consumer then permits reconnect after expiry\n";
}
'''
with tempfile.TemporaryDirectory(prefix='lrx-routing-') as temporary:
    source=Path(temporary)/'check.cpp';binary=Path(temporary)/'check';source.write_text(code)
    subprocess.run(['g++','-std=c++17','-I',str(root),str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
