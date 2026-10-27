#!/usr/bin/env python3
"""Exercise the production CSF parser with reserved compiler words and retail headers."""
# GeneralsX @bugfix Codex 27/10/2026 Reproduce the Community Patch zero-label failure.
import unittest
from compiled_harness import ROOT, run_cpp

SOURCE = (ROOT / 'Core/GameEngine/Source/GameClient/GameText.cpp').read_text()
a = SOURCE.index('struct CSFHeader\n')
HEADER = SOURCE[a:SOURCE.index('\n};', a) + 3]
a = SOURCE.index('Bool GameTextManager::parseCSF(')
PARSER = SOURCE[a:SOURCE.index('\n}', a) + 2]
FIXTURE = r'''
#include <cassert>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
using Int=int;using Bool=bool;using Char=char;using WideChar=wchar_t;using FileInstance=int;
#define TRUE true
#define FALSE false
const int MAX_UITEXT_LENGTH=1024, CSF_LABEL=0x4c424c20,CSF_STRING=0x53545220,CSF_STRINGWITHWAVE=0x53545257;
struct StringInfo{std::string label,speech;std::wstring text;};
struct File{
 enum{READ=1,BINARY=2,BUFFERSIZE=0,CURRENT=1};std::vector<unsigned char> bytes;size_t position=0;bool closed=false;
 int read(void*out,size_t count){auto n=std::min(count,bytes.size()-position);std::memcpy(out,bytes.data()+position,n);position+=n;return int(n);}
 void close(){closed=true;}
 void seek(int,int){assert(false&&"Reserved word is not a seek distance");}
};
struct FileSystem{File file;File*openFile(const char*,int,int,int){return &file;}} filesystem;
FileSystem*TheFileSystem=&filesystem;
void stripSpaces(wchar_t*){} // Test strings have no surrounding spaces.
struct GameTextManager{
 char m_buffer[1024];wchar_t m_tbuffer[1024];
 bool parseCSF(const char*,StringInfo*,int,int&,int=0);
};
void word(int n){auto*p=reinterpret_cast<unsigned char*>(&n);filesystem.file.bytes.insert(filesystem.file.bytes.end(),p,p+4);}
void label(const std::string&name,const std::wstring&text,bool speech=false){
 word(CSF_LABEL);word(1);word(int(name.size()));for(char c:name)filesystem.file.bytes.push_back(c);
 word(speech?CSF_STRINGWITHWAVE:CSF_STRING);word(int(text.size()));
 for(auto c:text){uint16_t encoded=uint16_t(~c);filesystem.file.bytes.push_back(encoded&255);filesystem.file.bytes.push_back(encoded>>8);}
 if(speech){word(5);for(char c:std::string("voice"))filesystem.file.bytes.push_back(c);}
}
'''


class CsfTests(unittest.TestCase):
    def test_patch_and_retail_headers_load_labels(self):
        run_cpp(FIXTURE + HEADER + PARSER + r'''
int main(){
 for(int reserved:{0,0x5448594d,-1}){
  filesystem.file=File{};
  word(0x43534620);word(3);word(2);word(2);word(reserved);word(0);
  label("GUI:Patch104p",L"Patch104p: Work In Progress. For test purposes only.");
  label("GUI:Test",L"Second label",true);
  GameTextManager reader;StringInfo strings[2];int maximum=0;
  assert(reader.parseCSF("test.csf",strings,2,maximum));
  assert(strings[0].label=="GUI:Patch104p");
  assert(strings[0].text==L"Patch104p: Work In Progress. For test purposes only.");
  assert(strings[1].text==L"Second label"&&strings[1].speech=="voice");
  assert(filesystem.file.closed&&filesystem.file.position==filesystem.file.bytes.size());
 }
}
''')

    def test_missing_declared_labels_fail(self):
        run_cpp(FIXTURE + HEADER + PARSER + r'''
int main(){for(int count:{0,1}){
 filesystem.file=File{};word(0x43534620);word(3);word(2);word(2);word(0x5448594d);word(0);
 if(count)label("GUI:Test",L"Test");
 GameTextManager reader;StringInfo strings[2];int maximum=0;
 assert(!reader.parseCSF("test.csf",strings,2,maximum));assert(filesystem.file.closed);
}}
''')

    def test_extra_labels_do_not_overrun_table(self):
        run_cpp(FIXTURE + HEADER + PARSER + r'''
int main(){word(0x43534620);word(3);word(1);word(1);word(0);word(0);
 label("GUI:First",L"First");label("GUI:Extra",L"Extra");
 GameTextManager reader;StringInfo strings[1];int maximum=0;
 assert(!reader.parseCSF("test.csf",strings,1,maximum));assert(filesystem.file.closed);
}
''')


if __name__ == '__main__':
    unittest.main()
