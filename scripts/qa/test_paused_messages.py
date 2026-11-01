#!/usr/bin/env python3
"""Compile production message ownership/transfer functions with game-state providers."""
# GeneralsX @test Codex 01/11/2026 Cover bounded paused metadata, command barriers, translator delivery and unchanged replay/network entry paths.
import unittest
from compiled_harness import ROOT, run_cpp


def function(source, marker):
    start = source.index(marker)
    return source[start:source.index('\n}', start) + 2]


def fixture():
    source = (ROOT / 'GeneralsMD/Code/GameEngine/Source/Common/MessageStream.cpp').read_text()
    header = (ROOT / 'GeneralsMD/Code/GameEngine/Include/Common/MessageStream.h').read_text()
    arguments = header[header.index('union GameMessageArgumentType'):header.index('class GameMessageArgument :')]
    bodies = '\n'.join(function(source, marker) for marker in [
        'GameMessage::GameMessage(', 'GameMessage::~GameMessage()', 'GameMessageArgument *GameMessage::allocArg()',
        'void GameMessage::appendIntegerArgument(', 'void GameMessage::appendRealArgument(',
        'void GameMessage::appendLocationArgument(', 'void GameMessage::appendPixelArgument(',
        'void GameMessage::appendTimestampArgument(', 'const GameMessageArgumentType *GameMessage::getArgument(',
        'GameMessageList::GameMessageList()', 'GameMessageList::~GameMessageList()',
        'void GameMessageList::appendMessage(', 'void GameMessageList::removeMessage(',
        'GameMessage *MessageStream::appendMessage(', 'void MessageStream::propagateMessages()',
        'CommandList::CommandList()', 'CommandList::~CommandList()', 'void CommandList::reset()',
        'void CommandList::destroyAllMessages()', 'void CommandList::appendMessageList(',
    ])
    dispatcher = (ROOT / 'GeneralsMD/Code/GameEngine/Source/GameClient/GameClientDispatch.cpp').read_text()
    bodies += '\n' + function(dispatcher, 'GameMessageDisposition GameClientMessageDispatcher::translateGameMessage(')
    return r'''
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <vector>
#include <algorithm>
using Bool=bool;using Int=int;using Real=float;using UnsignedInt=unsigned;using UnsignedByte=unsigned char;
using ObjectID=int;using DrawableID=int;using WideChar=wchar_t;
struct Coord3D{float x,y,z;};struct ICoord2D{int x,y;};struct IRegion2D{ICoord2D lo,hi;};
#define CPP_11(x) x
#define DEBUG_CRASH(...) assert(false)
#define DEBUG_ASSERTCRASH(value,...) assert(value)
#define newInstance(Type) new Type
template<class T>void deleteInstance(T*p){delete p;}
ARGUMENTS
size_t liveMessages=0,liveArguments=0,peakMessages=0,peakArguments=0;
struct MessageLifetime{MessageLifetime(){peakMessages=std::max(peakMessages,++liveMessages);}~MessageLifetime(){--liveMessages;}};
struct GameMessageArgument{GameMessageArgumentType m_data{};GameMessageArgumentDataType m_type;
 GameMessageArgument(){peakArguments=std::max(peakArguments,++liveArguments);}~GameMessageArgument(){--liveArguments;}};
struct GameMessageList;
struct GameMessage{
 enum Type{MSG_FRAME_TICK=1,MSG_RAW_MOUSE_POSITION=2,MSG_NEW_GAME=3,MSG_CLEAR_GAME_DATA=4,
  MSG_BEGIN_NETWORK_MESSAGES=1000,MSG_MOVE=1001,MSG_SELECT=1002,MSG_QUIT=1003,MSG_LOGIC_CRC=1004,
  MSG_SET_REPLAY_CAMERA=1005,MSG_END_NETWORK_MESSAGES=1999};
 MessageLifetime lifetime;
 GameMessage*m_next=nullptr,*m_prev=nullptr;GameMessageList*m_list=nullptr;
 Type m_type;int m_playerIndex=0;std::vector<GameMessageArgument*>m_argList;
 explicit GameMessage(Type);~GameMessage();
 GameMessage*next(){return m_next;}GameMessage*prev(){return m_prev;}
 Type getType()const{return m_type;}int getPlayerIndex()const{return m_playerIndex;}
 void friend_setNext(GameMessage*p){m_next=p;}void friend_setPrev(GameMessage*p){m_prev=p;}
 void friend_setList(GameMessageList*p){m_list=p;}void friend_setPlayerIndex(int p){m_playerIndex=p;}
 GameMessageArgument*allocArg();void appendIntegerArgument(Int);void appendRealArgument(Real);
 void appendLocationArgument(const Coord3D&);void appendPixelArgument(const ICoord2D&);void appendTimestampArgument(UnsignedInt);
 const GameMessageArgumentType*getArgument(Int)const;
 size_t getArgumentCount()const{return m_argList.size();}
};
struct Player{int index=0;int getPlayerIndex(){return index;}}player;
struct PlayerList{Player*getLocalPlayer(){return &player;}}players;
auto*ThePlayerList=&players;
struct Logic{bool paused=true;bool isGamePaused(){return paused;}}logic;
Logic*TheGameLogic=&logic;
struct Recorder{int mode=0;bool isPlaybackMode()const{return mode==1||mode==2;}}recorder;
Recorder*TheRecorder=&recorder;
struct Network{}network;Network*TheNetwork=nullptr;
struct GameMessageList{
 GameMessage*m_firstMessage=nullptr,*m_lastMessage=nullptr;
 GameMessageList();virtual~GameMessageList();virtual void reset(){}
 virtual void appendMessage(GameMessage*);virtual void removeMessage(GameMessage*);
 GameMessage*getFirstMessage(){return m_firstMessage;}
};
enum GameMessageDisposition{KEEP_MESSAGE,DESTROY_MESSAGE};
struct GameMessageTranslator{virtual~GameMessageTranslator()=default;virtual GameMessageDisposition translateGameMessage(const GameMessage*)=0;};
struct GameClientMessageDispatcher:GameMessageTranslator{GameMessageDisposition translateGameMessage(const GameMessage*)override;};
struct CommandList:GameMessageList{
 CommandList();~CommandList();void reset()override;void destroyAllMessages();void appendMessageList(GameMessage*);
};
CommandList*TheCommandList=nullptr;
struct MessageStream:GameMessageList{
 struct TranslatorData{GameMessageTranslator*m_translator;TranslatorData*m_next;};
 TranslatorData*m_firstTranslator=nullptr;
 GameMessage*appendMessage(GameMessage::Type);void propagateMessages();
 bool isInvalidDebugCommand(GameMessage::Type){return false;}
};
BODIES
GameMessage*camera(MessageStream&stream,unsigned frame){
 auto*m=stream.appendMessage(GameMessage::MSG_SET_REPLAY_CAMERA);
 m->appendLocationArgument({Real(frame),2,3});m->appendRealArgument(Real(frame)+.25f);
 m->appendRealArgument(Real(frame)+.5f);m->appendRealArgument(Real(frame)+.75f);
 m->appendIntegerArgument(frame%5);m->appendPixelArgument({int(frame),22});
 m->appendLocationArgument({4,5,6});m->appendLocationArgument({7,8,9});return m;}
void emitFrame(MessageStream&stream,unsigned frame,bool saveCamera=true){
 stream.appendMessage(GameMessage::MSG_FRAME_TICK)->appendTimestampArgument(frame);
 if(saveCamera)camera(stream,frame);}
std::vector<GameMessage*>messages(GameMessageList&list){
 std::vector<GameMessage*>result;GameMessage*last=nullptr;
 for(auto*m=list.getFirstMessage();m;m=m->next()){
  assert(result.size()<500000);assert(m->prev()==last&&m->m_list==&list);result.push_back(m);last=m;}
 assert(last==list.m_lastMessage);return result;}
void latestCamera(GameMessage*msg,unsigned frame){
 assert(msg->getType()==GameMessage::MSG_SET_REPLAY_CAMERA&&msg->getArgumentCount()==8);
 assert(msg->getArgument(0)->location.x==Real(frame)&&msg->getArgument(1)->real==Real(frame)+.25f);
 assert(msg->getArgument(2)->real==Real(frame)+.5f&&msg->getArgument(3)->real==Real(frame)+.75f);
 assert(msg->getArgument(4)->integer==int(frame%5)&&msg->getArgument(5)->pixel.x==int(frame));
 assert(msg->getArgument(6)->location.z==6&&msg->getArgument(7)->location.z==9);
 assert(msg->m_argList[0]->m_type==ARGUMENTDATATYPE_LOCATION&&msg->m_argList[1]->m_type==ARGUMENTDATATYPE_REAL&&
  msg->m_argList[4]->m_type==ARGUMENTDATATYPE_INTEGER&&msg->m_argList[5]->m_type==ARGUMENTDATATYPE_PIXEL);}
void empty(){assert(liveMessages==0&&liveArguments==0);}
'''.replace('ARGUMENTS', arguments).replace('BODIES', bodies)


class PausedMessageTests(unittest.TestCase):
    def test_long_pause_bounds_messages_arguments_and_keeps_latest_camera(self):
        run_cpp(fixture() + r'''
int main(){{CommandList commands;TheCommandList=&commands;MessageStream stream;
 for(unsigned frame=0;frame<100000;++frame){emitFrame(stream,frame);stream.propagateMessages();
  assert(liveMessages==2&&liveArguments==9&&stream.getFirstMessage()==nullptr);}
 auto queued=messages(commands);assert(queued.size()==2&&queued[0]->getArgument(0)->timestamp==99999);
 latestCamera(queued[1],99999);assert(peakMessages<=4&&peakArguments<=18);
 commands.reset();assert(messages(commands).empty());empty();}empty();}
''')

    def test_commands_are_ordering_barriers_with_unchanged_payloads(self):
        run_cpp(fixture() + r'''
int main(){{CommandList commands;TheCommandList=&commands;MessageStream stream;
 emitFrame(stream,1);stream.propagateMessages();auto before=messages(commands);
 auto*move=stream.appendMessage(GameMessage::MSG_MOVE);move->appendIntegerArgument(1234);
 emitFrame(stream,2);stream.propagateMessages();
 for(unsigned frame=3;frame<100;++frame){emitFrame(stream,frame);stream.propagateMessages();}
 auto queued=messages(commands);assert(queued.size()==5&&queued[0]==before[0]&&queued[1]==before[1]&&queued[2]==move);
 latestCamera(queued[1],1);latestCamera(queued[4],99);assert(move->getArgument(0)->integer==1234);
 // Every non-metadata type is a barrier, including new-game, quit and CRC controls.
 for(auto type:{GameMessage::MSG_SELECT,GameMessage::MSG_NEW_GAME,GameMessage::MSG_CLEAR_GAME_DATA,GameMessage::MSG_QUIT,GameMessage::MSG_LOGIC_CRC}){
  auto*command=stream.appendMessage(type);command->appendIntegerArgument(456);
  emitFrame(stream,100);stream.propagateMessages();auto prior=messages(commands);
  emitFrame(stream,101);stream.propagateMessages();auto now=messages(commands);
  assert(now.size()==prior.size()&&now[now.size()-3]==command&&command->getArgument(0)->integer==456);
  for(size_t i=0;i+2<now.size();++i)assert(now[i]==prior[i]);latestCamera(now.back(),101);}
 commands.reset();empty();}empty();}
''')

    def test_active_network_playback_and_missing_logic_preserve_every_message(self):
        run_cpp(fixture() + r'''
int main(){{CommandList commands;TheCommandList=&commands;MessageStream stream;
 for(int mode=0;mode<5;++mode){
  TheNetwork=mode==1?&network:nullptr;TheGameLogic=mode==2?nullptr:&logic;logic.paused=mode!=0;
  recorder.mode=mode>=3?mode-2:0;
  std::vector<GameMessage*>expected;
  for(unsigned frame=0;frame<100;++frame){emitFrame(stream,frame);auto incoming=messages(stream);
   expected.insert(expected.end(),incoming.begin(),incoming.end());stream.propagateMessages();}
  assert(messages(commands)==expected&&liveMessages==200&&liveArguments==900);
  commands.reset();empty();}
 }empty();}
''')

    def test_player_changes_are_barriers_and_never_merge_camera_payloads(self):
        run_cpp(fixture() + r'''
int main(){{CommandList commands;TheCommandList=&commands;MessageStream stream;
 player.index=0;emitFrame(stream,1);stream.propagateMessages();auto first=messages(commands);
 player.index=1;emitFrame(stream,2);stream.propagateMessages();auto other=messages(commands);
 player.index=0;emitFrame(stream,3);stream.propagateMessages();emitFrame(stream,4);stream.propagateMessages();
 auto now=messages(commands);assert(now.size()==6&&now[0]==first[0]&&now[1]==first[1]&&now[2]==other[2]&&now[3]==other[3]);
 assert(now[3]->getPlayerIndex()==1&&now[5]->getPlayerIndex()==0);latestCamera(now[3],2);latestCamera(now[5],4);
 commands.reset();empty();}empty();}
''')

    def test_every_client_tick_reaches_translators_before_queue_coalescing(self):
        run_cpp(fixture() + r'''
struct ClientProbe:GameMessageTranslator{MessageStream&stream;unsigned ticks=0,raw=0;
 explicit ClientProbe(MessageStream&s):stream(s){}
 GameMessageDisposition translateGameMessage(const GameMessage*msg)override{
  if(msg->getType()==GameMessage::MSG_FRAME_TICK){++ticks;camera(stream,msg->getArgument(0)->timestamp);}
  if(msg->getType()==GameMessage::MSG_RAW_MOUSE_POSITION)++raw;
  return KEEP_MESSAGE;}};
int main(){{CommandList commands;TheCommandList=&commands;MessageStream stream;ClientProbe probe(stream);GameClientMessageDispatcher dispatcher;
 MessageStream::TranslatorData last{&dispatcher,nullptr},first{&probe,&last};stream.m_firstTranslator=&first;
 for(unsigned frame=0;frame<2000;++frame){emitFrame(stream,frame,false);
  stream.appendMessage(GameMessage::MSG_RAW_MOUSE_POSITION)->appendIntegerArgument(10);stream.propagateMessages();}
 assert(probe.ticks==2000&&probe.raw==2000&&liveMessages==2&&liveArguments==9);
 auto queued=messages(commands);latestCamera(queued.back(),1999);commands.reset();empty();}empty();}
''', ['-DRTS_DEBUG'])

    def test_pause_resume_reset_and_replay_direct_appends_have_safe_ownership(self):
        run_cpp(fixture() + r'''
int main(){{CommandList commands;TheCommandList=&commands;MessageStream stream;
 for(unsigned round=0;round<100;++round){logic.paused=true;
  for(unsigned frame=0;frame<20;++frame){emitFrame(stream,frame);stream.propagateMessages();}
  logic.paused=false;emitFrame(stream,20);stream.propagateMessages();auto queued=messages(commands);
  assert(queued.size()==4);latestCamera(queued[1],19);latestCamera(queued[3],20);commands.reset();empty();}
 logic.paused=true;
	// Several snapshots in one incoming list exercise deletion of earlier transferred nodes.
	emitFrame(stream,30);emitFrame(stream,31);emitFrame(stream,32);stream.propagateMessages();
	assert(messages(commands).size()==2);latestCamera(messages(commands).back(),32);commands.reset();empty();
 // Recorder playback and simulation call appendMessage directly, so their recorded sequence is retained verbatim.
	recorder.mode=1;
 std::vector<GameMessage*>expected;
 for(unsigned i=0;i<100;++i){auto*msg=new GameMessage(GameMessage::MSG_SET_REPLAY_CAMERA);msg->appendIntegerArgument(i);
  commands.appendMessage(msg);expected.push_back(msg);}
 assert(messages(commands)==expected&&liveMessages==100);
 emitFrame(stream,101);stream.propagateMessages();auto playback=messages(commands);
 assert(playback.size()==102);for(size_t i=0;i<expected.size();++i)assert(playback[i]==expected[i]);
 commands.reset();empty();recorder.mode=0;TheRecorder=nullptr;
 // Tick-only streams remain bounded with camera recording disabled.
 for(unsigned frame=0;frame<1000;++frame){emitFrame(stream,frame,false);stream.propagateMessages();assert(liveMessages==1&&liveArguments==1);}
 commands.reset();empty();}empty();}
''')


if __name__ == '__main__':
    unittest.main()
