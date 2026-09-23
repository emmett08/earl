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
        4,1,63,385,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,2,20,
        7,20,2,21,7,21,2,22,7,22,2,23,7,23,2,24,7,24,2,25,7,25,2,26,7,26,
        1,0,1,0,1,0,1,0,5,0,59,8,0,10,0,12,0,62,9,0,1,0,1,0,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,1,1,1,1,1,1,3,1,76,8,1,1,2,1,2,1,2,1,2,4,2,82,8,
        2,11,2,12,2,83,1,2,1,2,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,
        3,1,4,1,4,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,
        5,1,5,1,5,1,5,1,5,1,5,3,5,120,8,5,1,5,4,5,123,8,5,11,5,12,5,124,
        1,5,1,5,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,
        1,6,3,6,144,8,6,1,6,1,6,1,6,3,6,149,8,6,1,6,1,6,1,7,1,7,1,7,1,7,
        1,7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,3,7,166,8,7,1,7,5,7,169,8,7,
        10,7,12,7,172,9,7,1,7,1,7,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,8,1,
        8,3,8,186,8,8,1,8,1,8,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,
        9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,
        9,1,9,1,9,1,9,1,10,1,10,1,10,1,10,1,10,1,10,1,11,1,11,1,11,1,11,
        1,11,1,11,1,11,1,11,1,11,1,11,3,11,236,8,11,1,11,1,11,1,11,1,11,
        3,11,242,8,11,1,11,1,11,1,11,1,11,3,11,248,8,11,1,11,1,11,1,11,1,
        11,3,11,254,8,11,1,12,1,12,1,12,1,12,1,12,1,12,5,12,262,8,12,10,
        12,12,12,265,9,12,3,12,267,8,12,1,12,1,12,1,12,1,12,1,12,1,13,1,
        13,1,13,1,13,1,14,1,14,1,14,1,14,1,14,3,14,283,8,14,1,15,1,15,1,
        15,1,15,1,15,1,15,1,15,1,15,5,15,293,8,15,10,15,12,15,296,9,15,3,
        15,298,8,15,1,15,1,15,1,15,1,16,1,16,1,16,1,16,1,17,1,17,1,17,1,
        17,1,17,1,17,1,17,1,17,1,17,1,17,1,17,3,17,318,8,17,1,17,1,17,1,
        17,1,17,3,17,324,8,17,1,17,1,17,1,18,1,18,1,19,1,19,1,19,5,19,333,
        8,19,10,19,12,19,336,9,19,1,20,1,20,1,20,1,20,1,20,1,20,1,21,1,21,
        1,22,1,22,1,22,3,22,349,8,22,1,23,1,23,1,23,1,23,1,23,1,23,1,23,
        1,23,5,23,359,8,23,10,23,12,23,362,9,23,3,23,364,8,23,1,23,1,23,
        1,24,1,24,1,24,1,24,5,24,372,8,24,10,24,12,24,375,9,24,3,24,377,
        8,24,1,24,1,24,1,25,1,25,1,26,1,26,1,26,0,0,27,0,2,4,6,8,10,12,14,
        16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48,50,52,0,5,1,0,
        9,10,5,0,15,15,20,20,24,24,32,32,44,44,1,0,47,52,2,0,55,57,59,60,
        5,0,21,21,25,31,36,37,42,42,58,58,396,0,54,1,0,0,0,2,75,1,0,0,0,
        4,77,1,0,0,0,6,87,1,0,0,0,8,98,1,0,0,0,10,100,1,0,0,0,12,128,1,0,
        0,0,14,152,1,0,0,0,16,175,1,0,0,0,18,189,1,0,0,0,20,219,1,0,0,0,
        22,225,1,0,0,0,24,255,1,0,0,0,26,273,1,0,0,0,28,282,1,0,0,0,30,284,
        1,0,0,0,32,302,1,0,0,0,34,306,1,0,0,0,36,327,1,0,0,0,38,329,1,0,
        0,0,40,337,1,0,0,0,42,343,1,0,0,0,44,348,1,0,0,0,46,350,1,0,0,0,
        48,367,1,0,0,0,50,380,1,0,0,0,52,382,1,0,0,0,54,55,5,1,0,0,55,56,
        5,60,0,0,56,60,5,2,0,0,57,59,3,2,1,0,58,57,1,0,0,0,59,62,1,0,0,0,
        60,58,1,0,0,0,60,61,1,0,0,0,61,63,1,0,0,0,62,60,1,0,0,0,63,64,5,
        0,0,1,64,1,1,0,0,0,65,76,3,4,2,0,66,76,3,6,3,0,67,76,3,10,5,0,68,
        76,3,12,6,0,69,76,3,14,7,0,70,76,3,16,8,0,71,76,3,20,10,0,72,76,
        3,34,17,0,73,76,3,24,12,0,74,76,3,30,15,0,75,65,1,0,0,0,75,66,1,
        0,0,0,75,67,1,0,0,0,75,68,1,0,0,0,75,69,1,0,0,0,75,70,1,0,0,0,75,
        71,1,0,0,0,75,72,1,0,0,0,75,73,1,0,0,0,75,74,1,0,0,0,76,3,1,0,0,
        0,77,78,5,3,0,0,78,79,3,52,26,0,79,81,5,4,0,0,80,82,3,40,20,0,81,
        80,1,0,0,0,82,83,1,0,0,0,83,81,1,0,0,0,83,84,1,0,0,0,84,85,1,0,0,
        0,85,86,5,5,0,0,86,5,1,0,0,0,87,88,5,6,0,0,88,89,3,52,26,0,89,90,
        5,4,0,0,90,91,5,7,0,0,91,92,5,60,0,0,92,93,5,2,0,0,93,94,5,8,0,0,
        94,95,3,8,4,0,95,96,5,2,0,0,96,97,5,5,0,0,97,7,1,0,0,0,98,99,7,0,
        0,0,99,9,1,0,0,0,100,101,5,11,0,0,101,102,3,52,26,0,102,103,5,4,
        0,0,103,104,5,6,0,0,104,105,3,52,26,0,105,106,5,2,0,0,106,107,5,
        12,0,0,107,108,3,52,26,0,108,109,5,2,0,0,109,110,5,3,0,0,110,111,
        3,52,26,0,111,112,5,2,0,0,112,113,5,13,0,0,113,114,5,59,0,0,114,
        119,5,2,0,0,115,116,5,14,0,0,116,117,3,44,22,0,117,118,5,2,0,0,118,
        120,1,0,0,0,119,115,1,0,0,0,119,120,1,0,0,0,120,122,1,0,0,0,121,
        123,3,40,20,0,122,121,1,0,0,0,123,124,1,0,0,0,124,122,1,0,0,0,124,
        125,1,0,0,0,125,126,1,0,0,0,126,127,5,5,0,0,127,11,1,0,0,0,128,129,
        5,15,0,0,129,130,3,52,26,0,130,131,5,4,0,0,131,132,5,16,0,0,132,
        133,5,60,0,0,133,134,5,2,0,0,134,135,5,3,0,0,135,136,3,52,26,0,136,
        137,5,2,0,0,137,138,5,17,0,0,138,139,3,52,26,0,139,143,5,2,0,0,140,
        141,5,18,0,0,141,142,5,60,0,0,142,144,5,2,0,0,143,140,1,0,0,0,143,
        144,1,0,0,0,144,148,1,0,0,0,145,146,5,19,0,0,146,147,5,60,0,0,147,
        149,5,2,0,0,148,145,1,0,0,0,148,149,1,0,0,0,149,150,1,0,0,0,150,
        151,5,5,0,0,151,13,1,0,0,0,152,153,5,20,0,0,153,154,3,52,26,0,154,
        155,5,4,0,0,155,156,5,21,0,0,156,157,5,60,0,0,157,158,5,2,0,0,158,
        159,5,22,0,0,159,160,5,60,0,0,160,165,5,2,0,0,161,162,5,23,0,0,162,
        163,3,38,19,0,163,164,5,2,0,0,164,166,1,0,0,0,165,161,1,0,0,0,165,
        166,1,0,0,0,166,170,1,0,0,0,167,169,3,40,20,0,168,167,1,0,0,0,169,
        172,1,0,0,0,170,168,1,0,0,0,170,171,1,0,0,0,171,173,1,0,0,0,172,
        170,1,0,0,0,173,174,5,5,0,0,174,15,1,0,0,0,175,176,5,24,0,0,176,
        177,3,52,26,0,177,178,5,4,0,0,178,179,5,16,0,0,179,180,5,60,0,0,
        180,181,5,2,0,0,181,182,5,3,0,0,182,183,3,52,26,0,183,185,5,2,0,
        0,184,186,3,18,9,0,185,184,1,0,0,0,185,186,1,0,0,0,186,187,1,0,0,
        0,187,188,5,5,0,0,188,17,1,0,0,0,189,190,5,25,0,0,190,191,5,4,0,
        0,191,192,5,26,0,0,192,193,5,60,0,0,193,194,5,2,0,0,194,195,5,27,
        0,0,195,196,5,60,0,0,196,197,5,2,0,0,197,198,5,28,0,0,198,199,5,
        60,0,0,199,200,5,2,0,0,200,201,5,29,0,0,201,202,5,60,0,0,202,203,
        5,2,0,0,203,204,5,18,0,0,204,205,5,60,0,0,205,206,5,2,0,0,206,207,
        5,19,0,0,207,208,5,60,0,0,208,209,5,2,0,0,209,210,5,30,0,0,210,211,
        3,44,22,0,211,212,5,2,0,0,212,213,5,31,0,0,213,214,5,60,0,0,214,
        215,3,42,21,0,215,216,3,50,25,0,216,217,5,2,0,0,217,218,5,5,0,0,
        218,19,1,0,0,0,219,220,5,32,0,0,220,221,3,52,26,0,221,222,5,4,0,
        0,222,223,3,22,11,0,223,224,5,5,0,0,224,21,1,0,0,0,225,226,5,33,
        0,0,226,227,3,52,26,0,227,228,5,2,0,0,228,229,5,20,0,0,229,230,3,
        52,26,0,230,235,5,2,0,0,231,232,5,11,0,0,232,233,3,38,19,0,233,234,
        5,2,0,0,234,236,1,0,0,0,235,231,1,0,0,0,235,236,1,0,0,0,236,241,
        1,0,0,0,237,238,5,34,0,0,238,239,3,38,19,0,239,240,5,2,0,0,240,242,
        1,0,0,0,241,237,1,0,0,0,241,242,1,0,0,0,242,247,1,0,0,0,243,244,
        5,35,0,0,244,245,3,38,19,0,245,246,5,2,0,0,246,248,1,0,0,0,247,243,
        1,0,0,0,247,248,1,0,0,0,248,253,1,0,0,0,249,250,5,36,0,0,250,251,
        3,52,26,0,251,252,5,2,0,0,252,254,1,0,0,0,253,249,1,0,0,0,253,254,
        1,0,0,0,254,23,1,0,0,0,255,256,5,37,0,0,256,257,3,52,26,0,257,266,
        5,38,0,0,258,263,3,26,13,0,259,260,5,39,0,0,260,262,3,26,13,0,261,
        259,1,0,0,0,262,265,1,0,0,0,263,261,1,0,0,0,263,264,1,0,0,0,264,
        267,1,0,0,0,265,263,1,0,0,0,266,258,1,0,0,0,266,267,1,0,0,0,267,
        268,1,0,0,0,268,269,5,40,0,0,269,270,5,4,0,0,270,271,3,22,11,0,271,
        272,5,5,0,0,272,25,1,0,0,0,273,274,3,52,26,0,274,275,5,41,0,0,275,
        276,3,28,14,0,276,27,1,0,0,0,277,283,5,24,0,0,278,283,5,20,0,0,279,
        283,5,11,0,0,280,283,5,15,0,0,281,283,3,52,26,0,282,277,1,0,0,0,
        282,278,1,0,0,0,282,279,1,0,0,0,282,280,1,0,0,0,282,281,1,0,0,0,
        283,29,1,0,0,0,284,285,5,42,0,0,285,286,3,52,26,0,286,287,5,43,0,
        0,287,288,3,52,26,0,288,297,5,38,0,0,289,294,3,32,16,0,290,291,5,
        39,0,0,291,293,3,32,16,0,292,290,1,0,0,0,293,296,1,0,0,0,294,292,
        1,0,0,0,294,295,1,0,0,0,295,298,1,0,0,0,296,294,1,0,0,0,297,289,
        1,0,0,0,297,298,1,0,0,0,298,299,1,0,0,0,299,300,5,40,0,0,300,301,
        5,2,0,0,301,31,1,0,0,0,302,303,3,52,26,0,303,304,5,43,0,0,304,305,
        3,52,26,0,305,33,1,0,0,0,306,307,5,44,0,0,307,308,3,52,26,0,308,
        309,5,4,0,0,309,310,5,45,0,0,310,311,3,36,18,0,311,312,3,52,26,0,
        312,317,5,2,0,0,313,314,5,11,0,0,314,315,3,38,19,0,315,316,5,2,0,
        0,316,318,1,0,0,0,317,313,1,0,0,0,317,318,1,0,0,0,318,323,1,0,0,
        0,319,320,5,35,0,0,320,321,3,38,19,0,321,322,5,2,0,0,322,324,1,0,
        0,0,323,319,1,0,0,0,323,324,1,0,0,0,324,325,1,0,0,0,325,326,5,5,
        0,0,326,35,1,0,0,0,327,328,7,1,0,0,328,37,1,0,0,0,329,334,3,52,26,
        0,330,331,5,39,0,0,331,333,3,52,26,0,332,330,1,0,0,0,333,336,1,0,
        0,0,334,332,1,0,0,0,334,335,1,0,0,0,335,39,1,0,0,0,336,334,1,0,0,
        0,337,338,5,46,0,0,338,339,5,60,0,0,339,340,3,42,21,0,340,341,3,
        50,25,0,341,342,5,2,0,0,342,41,1,0,0,0,343,344,7,2,0,0,344,43,1,
        0,0,0,345,349,3,50,25,0,346,349,3,46,23,0,347,349,3,48,24,0,348,
        345,1,0,0,0,348,346,1,0,0,0,348,347,1,0,0,0,349,45,1,0,0,0,350,363,
        5,4,0,0,351,352,5,60,0,0,352,353,5,41,0,0,353,360,3,44,22,0,354,
        355,5,39,0,0,355,356,5,60,0,0,356,357,5,41,0,0,357,359,3,44,22,0,
        358,354,1,0,0,0,359,362,1,0,0,0,360,358,1,0,0,0,360,361,1,0,0,0,
        361,364,1,0,0,0,362,360,1,0,0,0,363,351,1,0,0,0,363,364,1,0,0,0,
        364,365,1,0,0,0,365,366,5,5,0,0,366,47,1,0,0,0,367,376,5,53,0,0,
        368,373,3,44,22,0,369,370,5,39,0,0,370,372,3,44,22,0,371,369,1,0,
        0,0,372,375,1,0,0,0,373,371,1,0,0,0,373,374,1,0,0,0,374,377,1,0,
        0,0,375,373,1,0,0,0,376,368,1,0,0,0,376,377,1,0,0,0,377,378,1,0,
        0,0,378,379,5,54,0,0,379,49,1,0,0,0,380,381,7,3,0,0,381,51,1,0,0,
        0,382,383,7,4,0,0,383,53,1,0,0,0,27,60,75,83,119,124,143,148,165,
        170,185,235,241,247,253,263,266,282,294,297,317,323,334,348,360,
        363,373,376
    ]

class EALParser ( Parser ):

    grammarFileName = "EAL.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'language'", "';'", "'environment'", 
                     "'{'", "'}'", "'tool'", "'version'", "'mode'", "'deterministic'", 
                     "'nondeterministic'", "'evidence'", "'kind'", "'max_age'", 
                     "'input'", "'assumption'", "'statement'", "'validate'", 
                     "'valid_from'", "'valid_until'", "'reasoning'", "'method'", 
                     "'rationale'", "'backing'", "'claim'", "'proposition'", 
                     "'subject'", "'quantity'", "'unit'", "'scope'", "'query'", 
                     "'result'", "'argument'", "'conclusion'", "'assumptions'", 
                     "'premises'", "'binding'", "'pattern'", "'('", "','", 
                     "')'", "':'", "'apply'", "'='", "'objection'", "'target'", 
                     "'require'", "'=='", "'!='", "'<='", "'>='", "'<'", 
                     "'>'", "'['", "']'", "'true'", "'false'", "'null'" ]

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
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "ID", "NUMBER", "STRING", 
                      "LINE_COMMENT", "BLOCK_COMMENT", "WS" ]

    RULE_program = 0
    RULE_declaration = 1
    RULE_environmentDecl = 2
    RULE_toolDecl = 3
    RULE_executionMode = 4
    RULE_evidenceDecl = 5
    RULE_assumptionDecl = 6
    RULE_reasoningDecl = 7
    RULE_claimDecl = 8
    RULE_propositionDecl = 9
    RULE_argumentDecl = 10
    RULE_argumentBody = 11
    RULE_patternDecl = 12
    RULE_patternParameter = 13
    RULE_parameterKind = 14
    RULE_applicationDecl = 15
    RULE_patternBinding = 16
    RULE_objectionDecl = 17
    RULE_targetKind = 18
    RULE_idList = 19
    RULE_predicate = 20
    RULE_comparator = 21
    RULE_jsonValue = 22
    RULE_jsonObject = 23
    RULE_jsonArray = 24
    RULE_jsonScalar = 25
    RULE_identifier = 26

    ruleNames =  [ "program", "declaration", "environmentDecl", "toolDecl", 
                   "executionMode", "evidenceDecl", "assumptionDecl", "reasoningDecl", 
                   "claimDecl", "propositionDecl", "argumentDecl", "argumentBody", 
                   "patternDecl", "patternParameter", "parameterKind", "applicationDecl", 
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
    T__54=55
    T__55=56
    T__56=57
    ID=58
    NUMBER=59
    STRING=60
    LINE_COMMENT=61
    BLOCK_COMMENT=62
    WS=63

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
            self.state = 54
            self.match(EALParser.T__0)
            self.state = 55
            self.match(EALParser.STRING)
            self.state = 56
            self.match(EALParser.T__1)
            self.state = 60
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 22131984336968) != 0):
                self.state = 57
                self.declaration()
                self.state = 62
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 63
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
            self.state = 75
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [3]:
                self.enterOuterAlt(localctx, 1)
                self.state = 65
                self.environmentDecl()
                pass
            elif token in [6]:
                self.enterOuterAlt(localctx, 2)
                self.state = 66
                self.toolDecl()
                pass
            elif token in [11]:
                self.enterOuterAlt(localctx, 3)
                self.state = 67
                self.evidenceDecl()
                pass
            elif token in [15]:
                self.enterOuterAlt(localctx, 4)
                self.state = 68
                self.assumptionDecl()
                pass
            elif token in [20]:
                self.enterOuterAlt(localctx, 5)
                self.state = 69
                self.reasoningDecl()
                pass
            elif token in [24]:
                self.enterOuterAlt(localctx, 6)
                self.state = 70
                self.claimDecl()
                pass
            elif token in [32]:
                self.enterOuterAlt(localctx, 7)
                self.state = 71
                self.argumentDecl()
                pass
            elif token in [44]:
                self.enterOuterAlt(localctx, 8)
                self.state = 72
                self.objectionDecl()
                pass
            elif token in [37]:
                self.enterOuterAlt(localctx, 9)
                self.state = 73
                self.patternDecl()
                pass
            elif token in [42]:
                self.enterOuterAlt(localctx, 10)
                self.state = 74
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
            self.state = 77
            self.match(EALParser.T__2)
            self.state = 78
            self.identifier()
            self.state = 79
            self.match(EALParser.T__3)
            self.state = 81 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 80
                self.predicate()
                self.state = 83 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==46):
                    break

            self.state = 85
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

        def executionMode(self):
            return self.getTypedRuleContext(EALParser.ExecutionModeContext,0)


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
            self.state = 87
            self.match(EALParser.T__5)
            self.state = 88
            self.identifier()
            self.state = 89
            self.match(EALParser.T__3)
            self.state = 90
            self.match(EALParser.T__6)
            self.state = 91
            self.match(EALParser.STRING)
            self.state = 92
            self.match(EALParser.T__1)
            self.state = 93
            self.match(EALParser.T__7)
            self.state = 94
            self.executionMode()
            self.state = 95
            self.match(EALParser.T__1)
            self.state = 96
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExecutionModeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return EALParser.RULE_executionMode

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExecutionMode" ):
                return visitor.visitExecutionMode(self)
            else:
                return visitor.visitChildren(self)




    def executionMode(self):

        localctx = EALParser.ExecutionModeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_executionMode)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 98
            _la = self._input.LA(1)
            if not(_la==9 or _la==10):
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
        self.enterRule(localctx, 10, self.RULE_evidenceDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 100
            self.match(EALParser.T__10)
            self.state = 101
            self.identifier()
            self.state = 102
            self.match(EALParser.T__3)
            self.state = 103
            self.match(EALParser.T__5)
            self.state = 104
            self.identifier()
            self.state = 105
            self.match(EALParser.T__1)
            self.state = 106
            self.match(EALParser.T__11)
            self.state = 107
            self.identifier()
            self.state = 108
            self.match(EALParser.T__1)
            self.state = 109
            self.match(EALParser.T__2)
            self.state = 110
            self.identifier()
            self.state = 111
            self.match(EALParser.T__1)
            self.state = 112
            self.match(EALParser.T__12)
            self.state = 113
            self.match(EALParser.NUMBER)
            self.state = 114
            self.match(EALParser.T__1)
            self.state = 119
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==14:
                self.state = 115
                self.match(EALParser.T__13)
                self.state = 116
                self.jsonValue()
                self.state = 117
                self.match(EALParser.T__1)


            self.state = 122 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 121
                self.predicate()
                self.state = 124 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==46):
                    break

            self.state = 126
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
        self.enterRule(localctx, 12, self.RULE_assumptionDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 128
            self.match(EALParser.T__14)
            self.state = 129
            self.identifier()
            self.state = 130
            self.match(EALParser.T__3)
            self.state = 131
            self.match(EALParser.T__15)
            self.state = 132
            self.match(EALParser.STRING)
            self.state = 133
            self.match(EALParser.T__1)
            self.state = 134
            self.match(EALParser.T__2)
            self.state = 135
            self.identifier()
            self.state = 136
            self.match(EALParser.T__1)
            self.state = 137
            self.match(EALParser.T__16)
            self.state = 138
            self.identifier()
            self.state = 139
            self.match(EALParser.T__1)
            self.state = 143
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==18:
                self.state = 140
                self.match(EALParser.T__17)
                self.state = 141
                self.match(EALParser.STRING)
                self.state = 142
                self.match(EALParser.T__1)


            self.state = 148
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==19:
                self.state = 145
                self.match(EALParser.T__18)
                self.state = 146
                self.match(EALParser.STRING)
                self.state = 147
                self.match(EALParser.T__1)


            self.state = 150
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
        self.enterRule(localctx, 14, self.RULE_reasoningDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 152
            self.match(EALParser.T__19)
            self.state = 153
            self.identifier()
            self.state = 154
            self.match(EALParser.T__3)
            self.state = 155
            self.match(EALParser.T__20)
            self.state = 156
            localctx.methodName = self.match(EALParser.STRING)
            self.state = 157
            self.match(EALParser.T__1)
            self.state = 158
            self.match(EALParser.T__21)
            self.state = 159
            localctx.rationaleText = self.match(EALParser.STRING)
            self.state = 160
            self.match(EALParser.T__1)
            self.state = 165
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==23:
                self.state = 161
                self.match(EALParser.T__22)
                self.state = 162
                self.idList()
                self.state = 163
                self.match(EALParser.T__1)


            self.state = 170
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==46:
                self.state = 167
                self.predicate()
                self.state = 172
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 173
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
        self.enterRule(localctx, 16, self.RULE_claimDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 175
            self.match(EALParser.T__23)
            self.state = 176
            self.identifier()
            self.state = 177
            self.match(EALParser.T__3)
            self.state = 178
            self.match(EALParser.T__15)
            self.state = 179
            self.match(EALParser.STRING)
            self.state = 180
            self.match(EALParser.T__1)
            self.state = 181
            self.match(EALParser.T__2)
            self.state = 182
            self.identifier()
            self.state = 183
            self.match(EALParser.T__1)
            self.state = 185
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==25:
                self.state = 184
                self.propositionDecl()


            self.state = 187
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
        self.enterRule(localctx, 18, self.RULE_propositionDecl)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 189
            self.match(EALParser.T__24)
            self.state = 190
            self.match(EALParser.T__3)
            self.state = 191
            self.match(EALParser.T__25)
            self.state = 192
            self.match(EALParser.STRING)
            self.state = 193
            self.match(EALParser.T__1)
            self.state = 194
            self.match(EALParser.T__26)
            self.state = 195
            self.match(EALParser.STRING)
            self.state = 196
            self.match(EALParser.T__1)
            self.state = 197
            self.match(EALParser.T__27)
            self.state = 198
            self.match(EALParser.STRING)
            self.state = 199
            self.match(EALParser.T__1)
            self.state = 200
            self.match(EALParser.T__28)
            self.state = 201
            self.match(EALParser.STRING)
            self.state = 202
            self.match(EALParser.T__1)
            self.state = 203
            self.match(EALParser.T__17)
            self.state = 204
            self.match(EALParser.STRING)
            self.state = 205
            self.match(EALParser.T__1)
            self.state = 206
            self.match(EALParser.T__18)
            self.state = 207
            self.match(EALParser.STRING)
            self.state = 208
            self.match(EALParser.T__1)
            self.state = 209
            self.match(EALParser.T__29)
            self.state = 210
            self.jsonValue()
            self.state = 211
            self.match(EALParser.T__1)
            self.state = 212
            self.match(EALParser.T__30)
            self.state = 213
            self.match(EALParser.STRING)
            self.state = 214
            self.comparator()
            self.state = 215
            self.jsonScalar()
            self.state = 216
            self.match(EALParser.T__1)
            self.state = 217
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
        self.enterRule(localctx, 20, self.RULE_argumentDecl)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 219
            self.match(EALParser.T__31)
            self.state = 220
            self.identifier()
            self.state = 221
            self.match(EALParser.T__3)
            self.state = 222
            self.argumentBody()
            self.state = 223
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
        self.enterRule(localctx, 22, self.RULE_argumentBody)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 225
            self.match(EALParser.T__32)
            self.state = 226
            localctx.conclusionRef = self.identifier()
            self.state = 227
            self.match(EALParser.T__1)
            self.state = 228
            self.match(EALParser.T__19)
            self.state = 229
            localctx.reasoningRef = self.identifier()
            self.state = 230
            self.match(EALParser.T__1)
            self.state = 235
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 231
                self.match(EALParser.T__10)
                self.state = 232
                localctx.evidenceRefs = self.idList()
                self.state = 233
                self.match(EALParser.T__1)


            self.state = 241
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==34:
                self.state = 237
                self.match(EALParser.T__33)
                self.state = 238
                localctx.assumptionRefs = self.idList()
                self.state = 239
                self.match(EALParser.T__1)


            self.state = 247
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==35:
                self.state = 243
                self.match(EALParser.T__34)
                self.state = 244
                localctx.premiseRefs = self.idList()
                self.state = 245
                self.match(EALParser.T__1)


            self.state = 253
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==36:
                self.state = 249
                self.match(EALParser.T__35)
                self.state = 250
                localctx.bindingRef = self.identifier()
                self.state = 251
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
        self.enterRule(localctx, 24, self.RULE_patternDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 255
            self.match(EALParser.T__36)
            self.state = 256
            self.identifier()
            self.state = 257
            self.match(EALParser.T__37)
            self.state = 266
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 288234984620163072) != 0):
                self.state = 258
                self.patternParameter()
                self.state = 263
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==39:
                    self.state = 259
                    self.match(EALParser.T__38)
                    self.state = 260
                    self.patternParameter()
                    self.state = 265
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 268
            self.match(EALParser.T__39)
            self.state = 269
            self.match(EALParser.T__3)
            self.state = 270
            self.argumentBody()
            self.state = 271
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
        self.enterRule(localctx, 26, self.RULE_patternParameter)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 273
            self.identifier()
            self.state = 274
            self.match(EALParser.T__40)
            self.state = 275
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
        self.enterRule(localctx, 28, self.RULE_parameterKind)
        try:
            self.state = 282
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [24]:
                self.enterOuterAlt(localctx, 1)
                self.state = 277
                self.match(EALParser.T__23)
                pass
            elif token in [20]:
                self.enterOuterAlt(localctx, 2)
                self.state = 278
                self.match(EALParser.T__19)
                pass
            elif token in [11]:
                self.enterOuterAlt(localctx, 3)
                self.state = 279
                self.match(EALParser.T__10)
                pass
            elif token in [15]:
                self.enterOuterAlt(localctx, 4)
                self.state = 280
                self.match(EALParser.T__14)
                pass
            elif token in [21, 25, 26, 27, 28, 29, 30, 31, 36, 37, 42, 58]:
                self.enterOuterAlt(localctx, 5)
                self.state = 281
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
        self.enterRule(localctx, 30, self.RULE_applicationDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 284
            self.match(EALParser.T__41)
            self.state = 285
            self.identifier()
            self.state = 286
            self.match(EALParser.T__42)
            self.state = 287
            self.identifier()
            self.state = 288
            self.match(EALParser.T__37)
            self.state = 297
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 288234984620163072) != 0):
                self.state = 289
                self.patternBinding()
                self.state = 294
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==39:
                    self.state = 290
                    self.match(EALParser.T__38)
                    self.state = 291
                    self.patternBinding()
                    self.state = 296
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 299
            self.match(EALParser.T__39)
            self.state = 300
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
        self.enterRule(localctx, 32, self.RULE_patternBinding)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 302
            self.identifier()
            self.state = 303
            self.match(EALParser.T__42)
            self.state = 304
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
        self.enterRule(localctx, 34, self.RULE_objectionDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 306
            self.match(EALParser.T__43)
            self.state = 307
            self.identifier()
            self.state = 308
            self.match(EALParser.T__3)
            self.state = 309
            self.match(EALParser.T__44)
            self.state = 310
            self.targetKind()
            self.state = 311
            self.identifier()
            self.state = 312
            self.match(EALParser.T__1)
            self.state = 317
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 313
                self.match(EALParser.T__10)
                self.state = 314
                localctx.evidenceRefs = self.idList()
                self.state = 315
                self.match(EALParser.T__1)


            self.state = 323
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==35:
                self.state = 319
                self.match(EALParser.T__34)
                self.state = 320
                localctx.premiseRefs = self.idList()
                self.state = 321
                self.match(EALParser.T__1)


            self.state = 325
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
        self.enterRule(localctx, 36, self.RULE_targetKind)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 327
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 17596498870272) != 0)):
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
        self.enterRule(localctx, 38, self.RULE_idList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 329
            self.identifier()
            self.state = 334
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==39:
                self.state = 330
                self.match(EALParser.T__38)
                self.state = 331
                self.identifier()
                self.state = 336
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
        self.enterRule(localctx, 40, self.RULE_predicate)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 337
            self.match(EALParser.T__45)
            self.state = 338
            self.match(EALParser.STRING)
            self.state = 339
            self.comparator()
            self.state = 340
            self.jsonScalar()
            self.state = 341
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
        self.enterRule(localctx, 42, self.RULE_comparator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 343
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 8866461766385664) != 0)):
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
        self.enterRule(localctx, 44, self.RULE_jsonValue)
        try:
            self.state = 348
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [55, 56, 57, 59, 60]:
                self.enterOuterAlt(localctx, 1)
                self.state = 345
                self.jsonScalar()
                pass
            elif token in [4]:
                self.enterOuterAlt(localctx, 2)
                self.state = 346
                self.jsonObject()
                pass
            elif token in [53]:
                self.enterOuterAlt(localctx, 3)
                self.state = 347
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
        self.enterRule(localctx, 46, self.RULE_jsonObject)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 350
            self.match(EALParser.T__3)
            self.state = 363
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==60:
                self.state = 351
                self.match(EALParser.STRING)
                self.state = 352
                self.match(EALParser.T__40)
                self.state = 353
                self.jsonValue()
                self.state = 360
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==39:
                    self.state = 354
                    self.match(EALParser.T__38)
                    self.state = 355
                    self.match(EALParser.STRING)
                    self.state = 356
                    self.match(EALParser.T__40)
                    self.state = 357
                    self.jsonValue()
                    self.state = 362
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 365
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
        self.enterRule(localctx, 48, self.RULE_jsonArray)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 367
            self.match(EALParser.T__52)
            self.state = 376
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 1990591035297759248) != 0):
                self.state = 368
                self.jsonValue()
                self.state = 373
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==39:
                    self.state = 369
                    self.match(EALParser.T__38)
                    self.state = 370
                    self.jsonValue()
                    self.state = 375
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 378
            self.match(EALParser.T__53)
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
        self.enterRule(localctx, 50, self.RULE_jsonScalar)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 380
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 1981583836043018240) != 0)):
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
        self.enterRule(localctx, 52, self.RULE_identifier)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 382
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 288234984620163072) != 0)):
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





