# Generated from grammar/EAL.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,60,378,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,2,20,
        7,20,2,21,7,21,2,22,7,22,2,23,7,23,2,24,7,24,2,25,7,25,1,0,1,0,1,
        0,1,0,5,0,57,8,0,10,0,12,0,60,9,0,1,0,1,0,1,1,1,1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,1,3,1,74,8,1,1,2,1,2,1,2,1,2,4,2,80,8,2,11,2,12,
        2,81,1,2,1,2,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,4,1,4,1,4,1,4,1,4,
        1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,3,4,113,
        8,4,1,4,4,4,116,8,4,11,4,12,4,117,1,4,1,4,1,5,1,5,1,5,1,5,1,5,1,
        5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,3,5,137,8,5,1,5,1,5,1,5,3,
        5,142,8,5,1,5,1,5,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,
        6,1,6,3,6,159,8,6,1,6,5,6,162,8,6,10,6,12,6,165,9,6,1,6,1,6,1,7,
        1,7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,3,7,179,8,7,1,7,1,7,1,8,1,8,
        1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,
        1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,9,1,9,1,9,1,9,
        1,9,1,9,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,3,10,229,
        8,10,1,10,1,10,1,10,1,10,3,10,235,8,10,1,10,1,10,1,10,1,10,3,10,
        241,8,10,1,10,1,10,1,10,1,10,3,10,247,8,10,1,11,1,11,1,11,1,11,1,
        11,1,11,5,11,255,8,11,10,11,12,11,258,9,11,3,11,260,8,11,1,11,1,
        11,1,11,1,11,1,11,1,12,1,12,1,12,1,12,1,13,1,13,1,13,1,13,1,13,3,
        13,276,8,13,1,14,1,14,1,14,1,14,1,14,1,14,1,14,1,14,5,14,286,8,14,
        10,14,12,14,289,9,14,3,14,291,8,14,1,14,1,14,1,14,1,15,1,15,1,15,
        1,15,1,16,1,16,1,16,1,16,1,16,1,16,1,16,1,16,1,16,1,16,1,16,3,16,
        311,8,16,1,16,1,16,1,16,1,16,3,16,317,8,16,1,16,1,16,1,17,1,17,1,
        18,1,18,1,18,5,18,326,8,18,10,18,12,18,329,9,18,1,19,1,19,1,19,1,
        19,1,19,1,19,1,20,1,20,1,21,1,21,1,21,3,21,342,8,21,1,22,1,22,1,
        22,1,22,1,22,1,22,1,22,1,22,5,22,352,8,22,10,22,12,22,355,9,22,3,
        22,357,8,22,1,22,1,22,1,23,1,23,1,23,1,23,5,23,365,8,23,10,23,12,
        23,368,9,23,3,23,370,8,23,1,23,1,23,1,24,1,24,1,25,1,25,1,25,0,0,
        26,0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,
        44,46,48,50,0,4,5,0,12,12,17,17,21,21,29,29,41,41,1,0,44,49,2,0,
        52,54,56,57,5,0,18,18,22,28,33,34,39,39,55,55,390,0,52,1,0,0,0,2,
        73,1,0,0,0,4,75,1,0,0,0,6,85,1,0,0,0,8,93,1,0,0,0,10,121,1,0,0,0,
        12,145,1,0,0,0,14,168,1,0,0,0,16,182,1,0,0,0,18,212,1,0,0,0,20,218,
        1,0,0,0,22,248,1,0,0,0,24,266,1,0,0,0,26,275,1,0,0,0,28,277,1,0,
        0,0,30,295,1,0,0,0,32,299,1,0,0,0,34,320,1,0,0,0,36,322,1,0,0,0,
        38,330,1,0,0,0,40,336,1,0,0,0,42,341,1,0,0,0,44,343,1,0,0,0,46,360,
        1,0,0,0,48,373,1,0,0,0,50,375,1,0,0,0,52,53,5,1,0,0,53,54,5,57,0,
        0,54,58,5,2,0,0,55,57,3,2,1,0,56,55,1,0,0,0,57,60,1,0,0,0,58,56,
        1,0,0,0,58,59,1,0,0,0,59,61,1,0,0,0,60,58,1,0,0,0,61,62,5,0,0,1,
        62,1,1,0,0,0,63,74,3,4,2,0,64,74,3,6,3,0,65,74,3,8,4,0,66,74,3,10,
        5,0,67,74,3,12,6,0,68,74,3,14,7,0,69,74,3,18,9,0,70,74,3,32,16,0,
        71,74,3,22,11,0,72,74,3,28,14,0,73,63,1,0,0,0,73,64,1,0,0,0,73,65,
        1,0,0,0,73,66,1,0,0,0,73,67,1,0,0,0,73,68,1,0,0,0,73,69,1,0,0,0,
        73,70,1,0,0,0,73,71,1,0,0,0,73,72,1,0,0,0,74,3,1,0,0,0,75,76,5,3,
        0,0,76,77,3,50,25,0,77,79,5,4,0,0,78,80,3,38,19,0,79,78,1,0,0,0,
        80,81,1,0,0,0,81,79,1,0,0,0,81,82,1,0,0,0,82,83,1,0,0,0,83,84,5,
        5,0,0,84,5,1,0,0,0,85,86,5,6,0,0,86,87,3,50,25,0,87,88,5,4,0,0,88,
        89,5,7,0,0,89,90,5,57,0,0,90,91,5,2,0,0,91,92,5,5,0,0,92,7,1,0,0,
        0,93,94,5,8,0,0,94,95,3,50,25,0,95,96,5,4,0,0,96,97,5,6,0,0,97,98,
        3,50,25,0,98,99,5,2,0,0,99,100,5,9,0,0,100,101,3,50,25,0,101,102,
        5,2,0,0,102,103,5,3,0,0,103,104,3,50,25,0,104,105,5,2,0,0,105,106,
        5,10,0,0,106,107,5,56,0,0,107,112,5,2,0,0,108,109,5,11,0,0,109,110,
        3,42,21,0,110,111,5,2,0,0,111,113,1,0,0,0,112,108,1,0,0,0,112,113,
        1,0,0,0,113,115,1,0,0,0,114,116,3,38,19,0,115,114,1,0,0,0,116,117,
        1,0,0,0,117,115,1,0,0,0,117,118,1,0,0,0,118,119,1,0,0,0,119,120,
        5,5,0,0,120,9,1,0,0,0,121,122,5,12,0,0,122,123,3,50,25,0,123,124,
        5,4,0,0,124,125,5,13,0,0,125,126,5,57,0,0,126,127,5,2,0,0,127,128,
        5,3,0,0,128,129,3,50,25,0,129,130,5,2,0,0,130,131,5,14,0,0,131,132,
        3,50,25,0,132,136,5,2,0,0,133,134,5,15,0,0,134,135,5,57,0,0,135,
        137,5,2,0,0,136,133,1,0,0,0,136,137,1,0,0,0,137,141,1,0,0,0,138,
        139,5,16,0,0,139,140,5,57,0,0,140,142,5,2,0,0,141,138,1,0,0,0,141,
        142,1,0,0,0,142,143,1,0,0,0,143,144,5,5,0,0,144,11,1,0,0,0,145,146,
        5,17,0,0,146,147,3,50,25,0,147,148,5,4,0,0,148,149,5,18,0,0,149,
        150,5,57,0,0,150,151,5,2,0,0,151,152,5,19,0,0,152,153,5,57,0,0,153,
        158,5,2,0,0,154,155,5,20,0,0,155,156,3,36,18,0,156,157,5,2,0,0,157,
        159,1,0,0,0,158,154,1,0,0,0,158,159,1,0,0,0,159,163,1,0,0,0,160,
        162,3,38,19,0,161,160,1,0,0,0,162,165,1,0,0,0,163,161,1,0,0,0,163,
        164,1,0,0,0,164,166,1,0,0,0,165,163,1,0,0,0,166,167,5,5,0,0,167,
        13,1,0,0,0,168,169,5,21,0,0,169,170,3,50,25,0,170,171,5,4,0,0,171,
        172,5,13,0,0,172,173,5,57,0,0,173,174,5,2,0,0,174,175,5,3,0,0,175,
        176,3,50,25,0,176,178,5,2,0,0,177,179,3,16,8,0,178,177,1,0,0,0,178,
        179,1,0,0,0,179,180,1,0,0,0,180,181,5,5,0,0,181,15,1,0,0,0,182,183,
        5,22,0,0,183,184,5,4,0,0,184,185,5,23,0,0,185,186,5,57,0,0,186,187,
        5,2,0,0,187,188,5,24,0,0,188,189,5,57,0,0,189,190,5,2,0,0,190,191,
        5,25,0,0,191,192,5,57,0,0,192,193,5,2,0,0,193,194,5,26,0,0,194,195,
        5,57,0,0,195,196,5,2,0,0,196,197,5,15,0,0,197,198,5,57,0,0,198,199,
        5,2,0,0,199,200,5,16,0,0,200,201,5,57,0,0,201,202,5,2,0,0,202,203,
        5,27,0,0,203,204,3,42,21,0,204,205,5,2,0,0,205,206,5,28,0,0,206,
        207,5,57,0,0,207,208,3,40,20,0,208,209,3,48,24,0,209,210,5,2,0,0,
        210,211,5,5,0,0,211,17,1,0,0,0,212,213,5,29,0,0,213,214,3,50,25,
        0,214,215,5,4,0,0,215,216,3,20,10,0,216,217,5,5,0,0,217,19,1,0,0,
        0,218,219,5,30,0,0,219,220,3,50,25,0,220,221,5,2,0,0,221,222,5,17,
        0,0,222,223,3,50,25,0,223,228,5,2,0,0,224,225,5,8,0,0,225,226,3,
        36,18,0,226,227,5,2,0,0,227,229,1,0,0,0,228,224,1,0,0,0,228,229,
        1,0,0,0,229,234,1,0,0,0,230,231,5,31,0,0,231,232,3,36,18,0,232,233,
        5,2,0,0,233,235,1,0,0,0,234,230,1,0,0,0,234,235,1,0,0,0,235,240,
        1,0,0,0,236,237,5,32,0,0,237,238,3,36,18,0,238,239,5,2,0,0,239,241,
        1,0,0,0,240,236,1,0,0,0,240,241,1,0,0,0,241,246,1,0,0,0,242,243,
        5,33,0,0,243,244,3,50,25,0,244,245,5,2,0,0,245,247,1,0,0,0,246,242,
        1,0,0,0,246,247,1,0,0,0,247,21,1,0,0,0,248,249,5,34,0,0,249,250,
        3,50,25,0,250,259,5,35,0,0,251,256,3,24,12,0,252,253,5,36,0,0,253,
        255,3,24,12,0,254,252,1,0,0,0,255,258,1,0,0,0,256,254,1,0,0,0,256,
        257,1,0,0,0,257,260,1,0,0,0,258,256,1,0,0,0,259,251,1,0,0,0,259,
        260,1,0,0,0,260,261,1,0,0,0,261,262,5,37,0,0,262,263,5,4,0,0,263,
        264,3,20,10,0,264,265,5,5,0,0,265,23,1,0,0,0,266,267,3,50,25,0,267,
        268,5,38,0,0,268,269,3,26,13,0,269,25,1,0,0,0,270,276,5,21,0,0,271,
        276,5,17,0,0,272,276,5,8,0,0,273,276,5,12,0,0,274,276,3,50,25,0,
        275,270,1,0,0,0,275,271,1,0,0,0,275,272,1,0,0,0,275,273,1,0,0,0,
        275,274,1,0,0,0,276,27,1,0,0,0,277,278,5,39,0,0,278,279,3,50,25,
        0,279,280,5,40,0,0,280,281,3,50,25,0,281,290,5,35,0,0,282,287,3,
        30,15,0,283,284,5,36,0,0,284,286,3,30,15,0,285,283,1,0,0,0,286,289,
        1,0,0,0,287,285,1,0,0,0,287,288,1,0,0,0,288,291,1,0,0,0,289,287,
        1,0,0,0,290,282,1,0,0,0,290,291,1,0,0,0,291,292,1,0,0,0,292,293,
        5,37,0,0,293,294,5,2,0,0,294,29,1,0,0,0,295,296,3,50,25,0,296,297,
        5,40,0,0,297,298,3,50,25,0,298,31,1,0,0,0,299,300,5,41,0,0,300,301,
        3,50,25,0,301,302,5,4,0,0,302,303,5,42,0,0,303,304,3,34,17,0,304,
        305,3,50,25,0,305,310,5,2,0,0,306,307,5,8,0,0,307,308,3,36,18,0,
        308,309,5,2,0,0,309,311,1,0,0,0,310,306,1,0,0,0,310,311,1,0,0,0,
        311,316,1,0,0,0,312,313,5,32,0,0,313,314,3,36,18,0,314,315,5,2,0,
        0,315,317,1,0,0,0,316,312,1,0,0,0,316,317,1,0,0,0,317,318,1,0,0,
        0,318,319,5,5,0,0,319,33,1,0,0,0,320,321,7,0,0,0,321,35,1,0,0,0,
        322,327,3,50,25,0,323,324,5,36,0,0,324,326,3,50,25,0,325,323,1,0,
        0,0,326,329,1,0,0,0,327,325,1,0,0,0,327,328,1,0,0,0,328,37,1,0,0,
        0,329,327,1,0,0,0,330,331,5,43,0,0,331,332,5,57,0,0,332,333,3,40,
        20,0,333,334,3,48,24,0,334,335,5,2,0,0,335,39,1,0,0,0,336,337,7,
        1,0,0,337,41,1,0,0,0,338,342,3,48,24,0,339,342,3,44,22,0,340,342,
        3,46,23,0,341,338,1,0,0,0,341,339,1,0,0,0,341,340,1,0,0,0,342,43,
        1,0,0,0,343,356,5,4,0,0,344,345,5,57,0,0,345,346,5,38,0,0,346,353,
        3,42,21,0,347,348,5,36,0,0,348,349,5,57,0,0,349,350,5,38,0,0,350,
        352,3,42,21,0,351,347,1,0,0,0,352,355,1,0,0,0,353,351,1,0,0,0,353,
        354,1,0,0,0,354,357,1,0,0,0,355,353,1,0,0,0,356,344,1,0,0,0,356,
        357,1,0,0,0,357,358,1,0,0,0,358,359,5,5,0,0,359,45,1,0,0,0,360,369,
        5,50,0,0,361,366,3,42,21,0,362,363,5,36,0,0,363,365,3,42,21,0,364,
        362,1,0,0,0,365,368,1,0,0,0,366,364,1,0,0,0,366,367,1,0,0,0,367,
        370,1,0,0,0,368,366,1,0,0,0,369,361,1,0,0,0,369,370,1,0,0,0,370,
        371,1,0,0,0,371,372,5,51,0,0,372,47,1,0,0,0,373,374,7,2,0,0,374,
        49,1,0,0,0,375,376,7,3,0,0,376,51,1,0,0,0,27,58,73,81,112,117,136,
        141,158,163,178,228,234,240,246,256,259,275,287,290,310,316,327,
        341,353,356,366,369
    ]

class EALParser ( Parser ):

    grammarFileName = "EAL.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'language'", "';'", "'environment'", 
                     "'{'", "'}'", "'tool'", "'version'", "'evidence'", 
                     "'kind'", "'max_age'", "'input'", "'assumption'", "'statement'", 
                     "'validate'", "'valid_from'", "'valid_until'", "'reasoning'", 
                     "'method'", "'rationale'", "'backing'", "'claim'", 
                     "'proposition'", "'subject'", "'quantity'", "'unit'", 
                     "'scope'", "'query'", "'result'", "'argument'", "'conclusion'", 
                     "'assumptions'", "'premises'", "'binding'", "'pattern'", 
                     "'('", "','", "')'", "':'", "'apply'", "'='", "'objection'", 
                     "'target'", "'require'", "'=='", "'!='", "'<='", "'>='", 
                     "'<'", "'>'", "'['", "']'", "'true'", "'false'", "'null'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "ID", "NUMBER", 
                      "STRING", "LINE_COMMENT", "BLOCK_COMMENT", "WS" ]

    RULE_program = 0
    RULE_declaration = 1
    RULE_environmentDecl = 2
    RULE_toolDecl = 3
    RULE_evidenceDecl = 4
    RULE_assumptionDecl = 5
    RULE_reasoningDecl = 6
    RULE_claimDecl = 7
    RULE_propositionDecl = 8
    RULE_argumentDecl = 9
    RULE_argumentBody = 10
    RULE_patternDecl = 11
    RULE_patternParameter = 12
    RULE_parameterKind = 13
    RULE_applicationDecl = 14
    RULE_patternBinding = 15
    RULE_objectionDecl = 16
    RULE_targetKind = 17
    RULE_idList = 18
    RULE_predicate = 19
    RULE_comparator = 20
    RULE_jsonValue = 21
    RULE_jsonObject = 22
    RULE_jsonArray = 23
    RULE_jsonScalar = 24
    RULE_identifier = 25

    ruleNames =  [ "program", "declaration", "environmentDecl", "toolDecl", 
                   "evidenceDecl", "assumptionDecl", "reasoningDecl", "claimDecl", 
                   "propositionDecl", "argumentDecl", "argumentBody", "patternDecl", 
                   "patternParameter", "parameterKind", "applicationDecl", 
                   "patternBinding", "objectionDecl", "targetKind", "idList", 
                   "predicate", "comparator", "jsonValue", "jsonObject", 
                   "jsonArray", "jsonScalar", "identifier" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    T__4=5
    T__5=6
    T__6=7
    T__7=8
    T__8=9
    T__9=10
    T__10=11
    T__11=12
    T__12=13
    T__13=14
    T__14=15
    T__15=16
    T__16=17
    T__17=18
    T__18=19
    T__19=20
    T__20=21
    T__21=22
    T__22=23
    T__23=24
    T__24=25
    T__25=26
    T__26=27
    T__27=28
    T__28=29
    T__29=30
    T__30=31
    T__31=32
    T__32=33
    T__33=34
    T__34=35
    T__35=36
    T__36=37
    T__37=38
    T__38=39
    T__39=40
    T__40=41
    T__41=42
    T__42=43
    T__43=44
    T__44=45
    T__45=46
    T__46=47
    T__47=48
    T__48=49
    T__49=50
    T__50=51
    T__51=52
    T__52=53
    T__53=54
    ID=55
    NUMBER=56
    STRING=57
    LINE_COMMENT=58
    BLOCK_COMMENT=59
    WS=60

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ProgramContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(EALParser.STRING, 0)

        def EOF(self):
            return self.getToken(EALParser.EOF, 0)

        def declaration(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.DeclarationContext)
            else:
                return self.getTypedRuleContext(EALParser.DeclarationContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_program

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitProgram" ):
                return visitor.visitProgram(self)
            else:
                return visitor.visitChildren(self)




    def program(self):

        localctx = EALParser.ProgramContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_program)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 52
            self.match(EALParser.T__0)
            self.state = 53
            self.match(EALParser.STRING)
            self.state = 54
            self.match(EALParser.T__1)
            self.state = 58
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 2766498042184) != 0):
                self.state = 55
                self.declaration()
                self.state = 60
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 61
            self.match(EALParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def environmentDecl(self):
            return self.getTypedRuleContext(EALParser.EnvironmentDeclContext,0)


        def toolDecl(self):
            return self.getTypedRuleContext(EALParser.ToolDeclContext,0)


        def evidenceDecl(self):
            return self.getTypedRuleContext(EALParser.EvidenceDeclContext,0)


        def assumptionDecl(self):
            return self.getTypedRuleContext(EALParser.AssumptionDeclContext,0)


        def reasoningDecl(self):
            return self.getTypedRuleContext(EALParser.ReasoningDeclContext,0)


        def claimDecl(self):
            return self.getTypedRuleContext(EALParser.ClaimDeclContext,0)


        def argumentDecl(self):
            return self.getTypedRuleContext(EALParser.ArgumentDeclContext,0)


        def objectionDecl(self):
            return self.getTypedRuleContext(EALParser.ObjectionDeclContext,0)


        def patternDecl(self):
            return self.getTypedRuleContext(EALParser.PatternDeclContext,0)


        def applicationDecl(self):
            return self.getTypedRuleContext(EALParser.ApplicationDeclContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_declaration

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDeclaration" ):
                return visitor.visitDeclaration(self)
            else:
                return visitor.visitChildren(self)




    def declaration(self):

        localctx = EALParser.DeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_declaration)
        try:
            self.state = 73
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [3]:
                self.enterOuterAlt(localctx, 1)
                self.state = 63
                self.environmentDecl()
                pass
            elif token in [6]:
                self.enterOuterAlt(localctx, 2)
                self.state = 64
                self.toolDecl()
                pass
            elif token in [8]:
                self.enterOuterAlt(localctx, 3)
                self.state = 65
                self.evidenceDecl()
                pass
            elif token in [12]:
                self.enterOuterAlt(localctx, 4)
                self.state = 66
                self.assumptionDecl()
                pass
            elif token in [17]:
                self.enterOuterAlt(localctx, 5)
                self.state = 67
                self.reasoningDecl()
                pass
            elif token in [21]:
                self.enterOuterAlt(localctx, 6)
                self.state = 68
                self.claimDecl()
                pass
            elif token in [29]:
                self.enterOuterAlt(localctx, 7)
                self.state = 69
                self.argumentDecl()
                pass
            elif token in [41]:
                self.enterOuterAlt(localctx, 8)
                self.state = 70
                self.objectionDecl()
                pass
            elif token in [34]:
                self.enterOuterAlt(localctx, 9)
                self.state = 71
                self.patternDecl()
                pass
            elif token in [39]:
                self.enterOuterAlt(localctx, 10)
                self.state = 72
                self.applicationDecl()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EnvironmentDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self):
            return self.getTypedRuleContext(EALParser.IdentifierContext,0)


        def predicate(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.PredicateContext)
            else:
                return self.getTypedRuleContext(EALParser.PredicateContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_environmentDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEnvironmentDecl" ):
                return visitor.visitEnvironmentDecl(self)
            else:
                return visitor.visitChildren(self)




    def environmentDecl(self):

        localctx = EALParser.EnvironmentDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_environmentDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 75
            self.match(EALParser.T__2)
            self.state = 76
            self.identifier()
            self.state = 77
            self.match(EALParser.T__3)
            self.state = 79 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 78
                self.predicate()
                self.state = 81 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==43):
                    break

            self.state = 83
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ToolDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self):
            return self.getTypedRuleContext(EALParser.IdentifierContext,0)


        def STRING(self):
            return self.getToken(EALParser.STRING, 0)

        def getRuleIndex(self):
            return EALParser.RULE_toolDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitToolDecl" ):
                return visitor.visitToolDecl(self)
            else:
                return visitor.visitChildren(self)




    def toolDecl(self):

        localctx = EALParser.ToolDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_toolDecl)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 85
            self.match(EALParser.T__5)
            self.state = 86
            self.identifier()
            self.state = 87
            self.match(EALParser.T__3)
            self.state = 88
            self.match(EALParser.T__6)
            self.state = 89
            self.match(EALParser.STRING)
            self.state = 90
            self.match(EALParser.T__1)
            self.state = 91
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EvidenceDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def NUMBER(self):
            return self.getToken(EALParser.NUMBER, 0)

        def jsonValue(self):
            return self.getTypedRuleContext(EALParser.JsonValueContext,0)


        def predicate(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.PredicateContext)
            else:
                return self.getTypedRuleContext(EALParser.PredicateContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_evidenceDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEvidenceDecl" ):
                return visitor.visitEvidenceDecl(self)
            else:
                return visitor.visitChildren(self)




    def evidenceDecl(self):

        localctx = EALParser.EvidenceDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_evidenceDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 93
            self.match(EALParser.T__7)
            self.state = 94
            self.identifier()
            self.state = 95
            self.match(EALParser.T__3)
            self.state = 96
            self.match(EALParser.T__5)
            self.state = 97
            self.identifier()
            self.state = 98
            self.match(EALParser.T__1)
            self.state = 99
            self.match(EALParser.T__8)
            self.state = 100
            self.identifier()
            self.state = 101
            self.match(EALParser.T__1)
            self.state = 102
            self.match(EALParser.T__2)
            self.state = 103
            self.identifier()
            self.state = 104
            self.match(EALParser.T__1)
            self.state = 105
            self.match(EALParser.T__9)
            self.state = 106
            self.match(EALParser.NUMBER)
            self.state = 107
            self.match(EALParser.T__1)
            self.state = 112
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 108
                self.match(EALParser.T__10)
                self.state = 109
                self.jsonValue()
                self.state = 110
                self.match(EALParser.T__1)


            self.state = 115 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 114
                self.predicate()
                self.state = 117 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==43):
                    break

            self.state = 119
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AssumptionDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def STRING(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.STRING)
            else:
                return self.getToken(EALParser.STRING, i)

        def getRuleIndex(self):
            return EALParser.RULE_assumptionDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssumptionDecl" ):
                return visitor.visitAssumptionDecl(self)
            else:
                return visitor.visitChildren(self)




    def assumptionDecl(self):

        localctx = EALParser.AssumptionDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_assumptionDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 121
            self.match(EALParser.T__11)
            self.state = 122
            self.identifier()
            self.state = 123
            self.match(EALParser.T__3)
            self.state = 124
            self.match(EALParser.T__12)
            self.state = 125
            self.match(EALParser.STRING)
            self.state = 126
            self.match(EALParser.T__1)
            self.state = 127
            self.match(EALParser.T__2)
            self.state = 128
            self.identifier()
            self.state = 129
            self.match(EALParser.T__1)
            self.state = 130
            self.match(EALParser.T__13)
            self.state = 131
            self.identifier()
            self.state = 132
            self.match(EALParser.T__1)
            self.state = 136
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==15:
                self.state = 133
                self.match(EALParser.T__14)
                self.state = 134
                self.match(EALParser.STRING)
                self.state = 135
                self.match(EALParser.T__1)


            self.state = 141
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==16:
                self.state = 138
                self.match(EALParser.T__15)
                self.state = 139
                self.match(EALParser.STRING)
                self.state = 140
                self.match(EALParser.T__1)


            self.state = 143
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ReasoningDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.methodName = None # Token
            self.rationaleText = None # Token

        def identifier(self):
            return self.getTypedRuleContext(EALParser.IdentifierContext,0)


        def STRING(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.STRING)
            else:
                return self.getToken(EALParser.STRING, i)

        def idList(self):
            return self.getTypedRuleContext(EALParser.IdListContext,0)


        def predicate(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.PredicateContext)
            else:
                return self.getTypedRuleContext(EALParser.PredicateContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_reasoningDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitReasoningDecl" ):
                return visitor.visitReasoningDecl(self)
            else:
                return visitor.visitChildren(self)




    def reasoningDecl(self):

        localctx = EALParser.ReasoningDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_reasoningDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 145
            self.match(EALParser.T__16)
            self.state = 146
            self.identifier()
            self.state = 147
            self.match(EALParser.T__3)
            self.state = 148
            self.match(EALParser.T__17)
            self.state = 149
            localctx.methodName = self.match(EALParser.STRING)
            self.state = 150
            self.match(EALParser.T__1)
            self.state = 151
            self.match(EALParser.T__18)
            self.state = 152
            localctx.rationaleText = self.match(EALParser.STRING)
            self.state = 153
            self.match(EALParser.T__1)
            self.state = 158
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==20:
                self.state = 154
                self.match(EALParser.T__19)
                self.state = 155
                self.idList()
                self.state = 156
                self.match(EALParser.T__1)


            self.state = 163
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==43:
                self.state = 160
                self.predicate()
                self.state = 165
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 166
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ClaimDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def STRING(self):
            return self.getToken(EALParser.STRING, 0)

        def propositionDecl(self):
            return self.getTypedRuleContext(EALParser.PropositionDeclContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_claimDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitClaimDecl" ):
                return visitor.visitClaimDecl(self)
            else:
                return visitor.visitChildren(self)




    def claimDecl(self):

        localctx = EALParser.ClaimDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_claimDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 168
            self.match(EALParser.T__20)
            self.state = 169
            self.identifier()
            self.state = 170
            self.match(EALParser.T__3)
            self.state = 171
            self.match(EALParser.T__12)
            self.state = 172
            self.match(EALParser.STRING)
            self.state = 173
            self.match(EALParser.T__1)
            self.state = 174
            self.match(EALParser.T__2)
            self.state = 175
            self.identifier()
            self.state = 176
            self.match(EALParser.T__1)
            self.state = 178
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==22:
                self.state = 177
                self.propositionDecl()


            self.state = 180
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PropositionDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.STRING)
            else:
                return self.getToken(EALParser.STRING, i)

        def jsonValue(self):
            return self.getTypedRuleContext(EALParser.JsonValueContext,0)


        def comparator(self):
            return self.getTypedRuleContext(EALParser.ComparatorContext,0)


        def jsonScalar(self):
            return self.getTypedRuleContext(EALParser.JsonScalarContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_propositionDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPropositionDecl" ):
                return visitor.visitPropositionDecl(self)
            else:
                return visitor.visitChildren(self)




    def propositionDecl(self):

        localctx = EALParser.PropositionDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_propositionDecl)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 182
            self.match(EALParser.T__21)
            self.state = 183
            self.match(EALParser.T__3)
            self.state = 184
            self.match(EALParser.T__22)
            self.state = 185
            self.match(EALParser.STRING)
            self.state = 186
            self.match(EALParser.T__1)
            self.state = 187
            self.match(EALParser.T__23)
            self.state = 188
            self.match(EALParser.STRING)
            self.state = 189
            self.match(EALParser.T__1)
            self.state = 190
            self.match(EALParser.T__24)
            self.state = 191
            self.match(EALParser.STRING)
            self.state = 192
            self.match(EALParser.T__1)
            self.state = 193
            self.match(EALParser.T__25)
            self.state = 194
            self.match(EALParser.STRING)
            self.state = 195
            self.match(EALParser.T__1)
            self.state = 196
            self.match(EALParser.T__14)
            self.state = 197
            self.match(EALParser.STRING)
            self.state = 198
            self.match(EALParser.T__1)
            self.state = 199
            self.match(EALParser.T__15)
            self.state = 200
            self.match(EALParser.STRING)
            self.state = 201
            self.match(EALParser.T__1)
            self.state = 202
            self.match(EALParser.T__26)
            self.state = 203
            self.jsonValue()
            self.state = 204
            self.match(EALParser.T__1)
            self.state = 205
            self.match(EALParser.T__27)
            self.state = 206
            self.match(EALParser.STRING)
            self.state = 207
            self.comparator()
            self.state = 208
            self.jsonScalar()
            self.state = 209
            self.match(EALParser.T__1)
            self.state = 210
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArgumentDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self):
            return self.getTypedRuleContext(EALParser.IdentifierContext,0)


        def argumentBody(self):
            return self.getTypedRuleContext(EALParser.ArgumentBodyContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_argumentDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArgumentDecl" ):
                return visitor.visitArgumentDecl(self)
            else:
                return visitor.visitChildren(self)




    def argumentDecl(self):

        localctx = EALParser.ArgumentDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_argumentDecl)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 212
            self.match(EALParser.T__28)
            self.state = 213
            self.identifier()
            self.state = 214
            self.match(EALParser.T__3)
            self.state = 215
            self.argumentBody()
            self.state = 216
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArgumentBodyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.conclusionRef = None # IdentifierContext
            self.reasoningRef = None # IdentifierContext
            self.evidenceRefs = None # IdListContext
            self.assumptionRefs = None # IdListContext
            self.premiseRefs = None # IdListContext
            self.bindingRef = None # IdentifierContext

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def idList(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdListContext)
            else:
                return self.getTypedRuleContext(EALParser.IdListContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_argumentBody

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArgumentBody" ):
                return visitor.visitArgumentBody(self)
            else:
                return visitor.visitChildren(self)




    def argumentBody(self):

        localctx = EALParser.ArgumentBodyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_argumentBody)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 218
            self.match(EALParser.T__29)
            self.state = 219
            localctx.conclusionRef = self.identifier()
            self.state = 220
            self.match(EALParser.T__1)
            self.state = 221
            self.match(EALParser.T__16)
            self.state = 222
            localctx.reasoningRef = self.identifier()
            self.state = 223
            self.match(EALParser.T__1)
            self.state = 228
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==8:
                self.state = 224
                self.match(EALParser.T__7)
                self.state = 225
                localctx.evidenceRefs = self.idList()
                self.state = 226
                self.match(EALParser.T__1)


            self.state = 234
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==31:
                self.state = 230
                self.match(EALParser.T__30)
                self.state = 231
                localctx.assumptionRefs = self.idList()
                self.state = 232
                self.match(EALParser.T__1)


            self.state = 240
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==32:
                self.state = 236
                self.match(EALParser.T__31)
                self.state = 237
                localctx.premiseRefs = self.idList()
                self.state = 238
                self.match(EALParser.T__1)


            self.state = 246
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==33:
                self.state = 242
                self.match(EALParser.T__32)
                self.state = 243
                localctx.bindingRef = self.identifier()
                self.state = 244
                self.match(EALParser.T__1)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PatternDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self):
            return self.getTypedRuleContext(EALParser.IdentifierContext,0)


        def argumentBody(self):
            return self.getTypedRuleContext(EALParser.ArgumentBodyContext,0)


        def patternParameter(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.PatternParameterContext)
            else:
                return self.getTypedRuleContext(EALParser.PatternParameterContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_patternDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPatternDecl" ):
                return visitor.visitPatternDecl(self)
            else:
                return visitor.visitChildren(self)




    def patternDecl(self):

        localctx = EALParser.PatternDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_patternDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 248
            self.match(EALParser.T__33)
            self.state = 249
            self.identifier()
            self.state = 250
            self.match(EALParser.T__34)
            self.state = 259
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 36029373077520384) != 0):
                self.state = 251
                self.patternParameter()
                self.state = 256
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==36:
                    self.state = 252
                    self.match(EALParser.T__35)
                    self.state = 253
                    self.patternParameter()
                    self.state = 258
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 261
            self.match(EALParser.T__36)
            self.state = 262
            self.match(EALParser.T__3)
            self.state = 263
            self.argumentBody()
            self.state = 264
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PatternParameterContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self):
            return self.getTypedRuleContext(EALParser.IdentifierContext,0)


        def parameterKind(self):
            return self.getTypedRuleContext(EALParser.ParameterKindContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_patternParameter

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPatternParameter" ):
                return visitor.visitPatternParameter(self)
            else:
                return visitor.visitChildren(self)




    def patternParameter(self):

        localctx = EALParser.PatternParameterContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_patternParameter)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 266
            self.identifier()
            self.state = 267
            self.match(EALParser.T__37)
            self.state = 268
            self.parameterKind()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParameterKindContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self):
            return self.getTypedRuleContext(EALParser.IdentifierContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_parameterKind

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParameterKind" ):
                return visitor.visitParameterKind(self)
            else:
                return visitor.visitChildren(self)




    def parameterKind(self):

        localctx = EALParser.ParameterKindContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_parameterKind)
        try:
            self.state = 275
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [21]:
                self.enterOuterAlt(localctx, 1)
                self.state = 270
                self.match(EALParser.T__20)
                pass
            elif token in [17]:
                self.enterOuterAlt(localctx, 2)
                self.state = 271
                self.match(EALParser.T__16)
                pass
            elif token in [8]:
                self.enterOuterAlt(localctx, 3)
                self.state = 272
                self.match(EALParser.T__7)
                pass
            elif token in [12]:
                self.enterOuterAlt(localctx, 4)
                self.state = 273
                self.match(EALParser.T__11)
                pass
            elif token in [18, 22, 23, 24, 25, 26, 27, 28, 33, 34, 39, 55]:
                self.enterOuterAlt(localctx, 5)
                self.state = 274
                self.identifier()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ApplicationDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def patternBinding(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.PatternBindingContext)
            else:
                return self.getTypedRuleContext(EALParser.PatternBindingContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_applicationDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitApplicationDecl" ):
                return visitor.visitApplicationDecl(self)
            else:
                return visitor.visitChildren(self)




    def applicationDecl(self):

        localctx = EALParser.ApplicationDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_applicationDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 277
            self.match(EALParser.T__38)
            self.state = 278
            self.identifier()
            self.state = 279
            self.match(EALParser.T__39)
            self.state = 280
            self.identifier()
            self.state = 281
            self.match(EALParser.T__34)
            self.state = 290
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 36029373077520384) != 0):
                self.state = 282
                self.patternBinding()
                self.state = 287
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==36:
                    self.state = 283
                    self.match(EALParser.T__35)
                    self.state = 284
                    self.patternBinding()
                    self.state = 289
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 292
            self.match(EALParser.T__36)
            self.state = 293
            self.match(EALParser.T__1)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PatternBindingContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_patternBinding

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPatternBinding" ):
                return visitor.visitPatternBinding(self)
            else:
                return visitor.visitChildren(self)




    def patternBinding(self):

        localctx = EALParser.PatternBindingContext(self, self._ctx, self.state)
        self.enterRule(localctx, 30, self.RULE_patternBinding)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 295
            self.identifier()
            self.state = 296
            self.match(EALParser.T__39)
            self.state = 297
            self.identifier()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ObjectionDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.evidenceRefs = None # IdListContext
            self.premiseRefs = None # IdListContext

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def targetKind(self):
            return self.getTypedRuleContext(EALParser.TargetKindContext,0)


        def idList(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdListContext)
            else:
                return self.getTypedRuleContext(EALParser.IdListContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_objectionDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitObjectionDecl" ):
                return visitor.visitObjectionDecl(self)
            else:
                return visitor.visitChildren(self)




    def objectionDecl(self):

        localctx = EALParser.ObjectionDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 32, self.RULE_objectionDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 299
            self.match(EALParser.T__40)
            self.state = 300
            self.identifier()
            self.state = 301
            self.match(EALParser.T__3)
            self.state = 302
            self.match(EALParser.T__41)
            self.state = 303
            self.targetKind()
            self.state = 304
            self.identifier()
            self.state = 305
            self.match(EALParser.T__1)
            self.state = 310
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==8:
                self.state = 306
                self.match(EALParser.T__7)
                self.state = 307
                localctx.evidenceRefs = self.idList()
                self.state = 308
                self.match(EALParser.T__1)


            self.state = 316
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==32:
                self.state = 312
                self.match(EALParser.T__31)
                self.state = 313
                localctx.premiseRefs = self.idList()
                self.state = 314
                self.match(EALParser.T__1)


            self.state = 318
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TargetKindContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return EALParser.RULE_targetKind

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTargetKind" ):
                return visitor.visitTargetKind(self)
            else:
                return visitor.visitChildren(self)




    def targetKind(self):

        localctx = EALParser.TargetKindContext(self, self._ctx, self.state)
        self.enterRule(localctx, 34, self.RULE_targetKind)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 320
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 2199562358784) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class IdListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_idList

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIdList" ):
                return visitor.visitIdList(self)
            else:
                return visitor.visitChildren(self)




    def idList(self):

        localctx = EALParser.IdListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 36, self.RULE_idList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 322
            self.identifier()
            self.state = 327
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==36:
                self.state = 323
                self.match(EALParser.T__35)
                self.state = 324
                self.identifier()
                self.state = 329
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PredicateContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(EALParser.STRING, 0)

        def comparator(self):
            return self.getTypedRuleContext(EALParser.ComparatorContext,0)


        def jsonScalar(self):
            return self.getTypedRuleContext(EALParser.JsonScalarContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_predicate

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPredicate" ):
                return visitor.visitPredicate(self)
            else:
                return visitor.visitChildren(self)




    def predicate(self):

        localctx = EALParser.PredicateContext(self, self._ctx, self.state)
        self.enterRule(localctx, 38, self.RULE_predicate)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 330
            self.match(EALParser.T__42)
            self.state = 331
            self.match(EALParser.STRING)
            self.state = 332
            self.comparator()
            self.state = 333
            self.jsonScalar()
            self.state = 334
            self.match(EALParser.T__1)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ComparatorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return EALParser.RULE_comparator

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitComparator" ):
                return visitor.visitComparator(self)
            else:
                return visitor.visitChildren(self)




    def comparator(self):

        localctx = EALParser.ComparatorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 40, self.RULE_comparator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 336
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 1108307720798208) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class JsonValueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def jsonScalar(self):
            return self.getTypedRuleContext(EALParser.JsonScalarContext,0)


        def jsonObject(self):
            return self.getTypedRuleContext(EALParser.JsonObjectContext,0)


        def jsonArray(self):
            return self.getTypedRuleContext(EALParser.JsonArrayContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_jsonValue

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitJsonValue" ):
                return visitor.visitJsonValue(self)
            else:
                return visitor.visitChildren(self)




    def jsonValue(self):

        localctx = EALParser.JsonValueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 42, self.RULE_jsonValue)
        try:
            self.state = 341
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [52, 53, 54, 56, 57]:
                self.enterOuterAlt(localctx, 1)
                self.state = 338
                self.jsonScalar()
                pass
            elif token in [4]:
                self.enterOuterAlt(localctx, 2)
                self.state = 339
                self.jsonObject()
                pass
            elif token in [50]:
                self.enterOuterAlt(localctx, 3)
                self.state = 340
                self.jsonArray()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class JsonObjectContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.STRING)
            else:
                return self.getToken(EALParser.STRING, i)

        def jsonValue(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.JsonValueContext)
            else:
                return self.getTypedRuleContext(EALParser.JsonValueContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_jsonObject

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitJsonObject" ):
                return visitor.visitJsonObject(self)
            else:
                return visitor.visitChildren(self)




    def jsonObject(self):

        localctx = EALParser.JsonObjectContext(self, self._ctx, self.state)
        self.enterRule(localctx, 44, self.RULE_jsonObject)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 343
            self.match(EALParser.T__3)
            self.state = 356
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==57:
                self.state = 344
                self.match(EALParser.STRING)
                self.state = 345
                self.match(EALParser.T__37)
                self.state = 346
                self.jsonValue()
                self.state = 353
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==36:
                    self.state = 347
                    self.match(EALParser.T__35)
                    self.state = 348
                    self.match(EALParser.STRING)
                    self.state = 349
                    self.match(EALParser.T__37)
                    self.state = 350
                    self.jsonValue()
                    self.state = 355
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 358
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class JsonArrayContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def jsonValue(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.JsonValueContext)
            else:
                return self.getTypedRuleContext(EALParser.JsonValueContext,i)


        def getRuleIndex(self):
            return EALParser.RULE_jsonArray

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitJsonArray" ):
                return visitor.visitJsonArray(self)
            else:
                return visitor.visitChildren(self)




    def jsonArray(self):

        localctx = EALParser.JsonArrayContext(self, self._ctx, self.state)
        self.enterRule(localctx, 46, self.RULE_jsonArray)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 360
            self.match(EALParser.T__49)
            self.state = 369
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 248823879412219920) != 0):
                self.state = 361
                self.jsonValue()
                self.state = 366
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==36:
                    self.state = 362
                    self.match(EALParser.T__35)
                    self.state = 363
                    self.jsonValue()
                    self.state = 368
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 371
            self.match(EALParser.T__50)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class JsonScalarContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(EALParser.STRING, 0)

        def NUMBER(self):
            return self.getToken(EALParser.NUMBER, 0)

        def getRuleIndex(self):
            return EALParser.RULE_jsonScalar

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitJsonScalar" ):
                return visitor.visitJsonScalar(self)
            else:
                return visitor.visitChildren(self)




    def jsonScalar(self):

        localctx = EALParser.JsonScalarContext(self, self._ctx, self.state)
        self.enterRule(localctx, 48, self.RULE_jsonScalar)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 373
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 247697979505377280) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class IdentifierContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EALParser.ID, 0)

        def getRuleIndex(self):
            return EALParser.RULE_identifier

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIdentifier" ):
                return visitor.visitIdentifier(self)
            else:
                return visitor.visitChildren(self)




    def identifier(self):

        localctx = EALParser.IdentifierContext(self, self._ctx, self.state)
        self.enterRule(localctx, 50, self.RULE_identifier)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 375
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 36029373077520384) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





