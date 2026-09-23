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
        4,1,65,314,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,2,20,
        7,20,2,21,7,21,1,0,1,0,1,0,1,0,5,0,49,8,0,10,0,12,0,52,9,0,1,0,1,
        0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,3,1,64,8,1,1,2,1,2,1,2,1,2,4,2,
        70,8,2,11,2,12,2,71,1,2,1,2,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,
        1,3,1,3,1,4,1,4,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,
        1,5,1,5,1,5,1,5,1,5,1,5,1,5,3,5,108,8,5,1,5,4,5,111,8,5,11,5,12,
        5,112,1,5,1,5,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,
        6,1,6,1,6,3,6,132,8,6,1,6,1,6,1,6,3,6,137,8,6,1,6,1,6,1,7,1,7,1,
        7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,3,7,154,8,7,1,7,5,7,157,
        8,7,10,7,12,7,160,9,7,1,7,1,7,1,8,1,8,1,9,1,9,1,9,1,9,1,9,1,9,1,
        9,1,9,1,9,1,9,3,9,176,8,9,1,9,1,9,1,10,1,10,1,10,1,10,1,10,1,10,
        1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,
        1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,11,1,11,
        1,11,1,11,1,11,1,11,1,11,1,11,1,11,1,11,1,11,1,11,1,11,3,11,223,
        8,11,1,11,1,11,1,11,1,11,3,11,229,8,11,1,11,1,11,1,11,1,11,3,11,
        235,8,11,1,11,1,11,1,11,1,11,3,11,241,8,11,1,11,1,11,1,12,1,12,1,
        12,1,12,1,12,1,12,1,12,1,12,1,12,1,12,1,12,1,12,1,13,1,13,1,14,1,
        14,1,14,5,14,262,8,14,10,14,12,14,265,9,14,1,15,1,15,1,15,1,15,1,
        15,1,15,1,16,1,16,1,17,1,17,1,17,3,17,278,8,17,1,18,1,18,1,18,1,
        18,1,18,1,18,1,18,1,18,5,18,288,8,18,10,18,12,18,291,9,18,3,18,293,
        8,18,1,18,1,18,1,19,1,19,1,19,1,19,5,19,301,8,19,10,19,12,19,304,
        9,19,3,19,306,8,19,1,19,1,19,1,20,1,20,1,21,1,21,1,21,0,0,22,0,2,
        4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,0,6,1,0,
        9,10,1,0,23,30,3,0,15,15,20,20,31,31,1,0,48,53,2,0,57,59,61,62,3,
        0,32,38,43,43,60,60,318,0,44,1,0,0,0,2,63,1,0,0,0,4,65,1,0,0,0,6,
        75,1,0,0,0,8,86,1,0,0,0,10,88,1,0,0,0,12,116,1,0,0,0,14,140,1,0,
        0,0,16,163,1,0,0,0,18,165,1,0,0,0,20,179,1,0,0,0,22,209,1,0,0,0,
        24,244,1,0,0,0,26,256,1,0,0,0,28,258,1,0,0,0,30,266,1,0,0,0,32,272,
        1,0,0,0,34,277,1,0,0,0,36,279,1,0,0,0,38,296,1,0,0,0,40,309,1,0,
        0,0,42,311,1,0,0,0,44,45,5,1,0,0,45,46,5,62,0,0,46,50,5,2,0,0,47,
        49,3,2,1,0,48,47,1,0,0,0,49,52,1,0,0,0,50,48,1,0,0,0,50,51,1,0,0,
        0,51,53,1,0,0,0,52,50,1,0,0,0,53,54,5,0,0,1,54,1,1,0,0,0,55,64,3,
        4,2,0,56,64,3,6,3,0,57,64,3,10,5,0,58,64,3,12,6,0,59,64,3,14,7,0,
        60,64,3,18,9,0,61,64,3,22,11,0,62,64,3,24,12,0,63,55,1,0,0,0,63,
        56,1,0,0,0,63,57,1,0,0,0,63,58,1,0,0,0,63,59,1,0,0,0,63,60,1,0,0,
        0,63,61,1,0,0,0,63,62,1,0,0,0,64,3,1,0,0,0,65,66,5,3,0,0,66,67,3,
        42,21,0,67,69,5,4,0,0,68,70,3,30,15,0,69,68,1,0,0,0,70,71,1,0,0,
        0,71,69,1,0,0,0,71,72,1,0,0,0,72,73,1,0,0,0,73,74,5,5,0,0,74,5,1,
        0,0,0,75,76,5,6,0,0,76,77,3,42,21,0,77,78,5,4,0,0,78,79,5,7,0,0,
        79,80,5,62,0,0,80,81,5,2,0,0,81,82,5,8,0,0,82,83,3,8,4,0,83,84,5,
        2,0,0,84,85,5,5,0,0,85,7,1,0,0,0,86,87,7,0,0,0,87,9,1,0,0,0,88,89,
        5,11,0,0,89,90,3,42,21,0,90,91,5,4,0,0,91,92,5,6,0,0,92,93,3,42,
        21,0,93,94,5,2,0,0,94,95,5,12,0,0,95,96,3,42,21,0,96,97,5,2,0,0,
        97,98,5,3,0,0,98,99,3,42,21,0,99,100,5,2,0,0,100,101,5,13,0,0,101,
        102,5,61,0,0,102,107,5,2,0,0,103,104,5,14,0,0,104,105,3,34,17,0,
        105,106,5,2,0,0,106,108,1,0,0,0,107,103,1,0,0,0,107,108,1,0,0,0,
        108,110,1,0,0,0,109,111,3,30,15,0,110,109,1,0,0,0,111,112,1,0,0,
        0,112,110,1,0,0,0,112,113,1,0,0,0,113,114,1,0,0,0,114,115,5,5,0,
        0,115,11,1,0,0,0,116,117,5,15,0,0,117,118,3,42,21,0,118,119,5,4,
        0,0,119,120,5,16,0,0,120,121,5,62,0,0,121,122,5,2,0,0,122,123,5,
        3,0,0,123,124,3,42,21,0,124,125,5,2,0,0,125,126,5,17,0,0,126,127,
        3,42,21,0,127,131,5,2,0,0,128,129,5,18,0,0,129,130,5,62,0,0,130,
        132,5,2,0,0,131,128,1,0,0,0,131,132,1,0,0,0,132,136,1,0,0,0,133,
        134,5,19,0,0,134,135,5,62,0,0,135,137,5,2,0,0,136,133,1,0,0,0,136,
        137,1,0,0,0,137,138,1,0,0,0,138,139,5,5,0,0,139,13,1,0,0,0,140,141,
        5,20,0,0,141,142,3,42,21,0,142,143,5,4,0,0,143,144,5,8,0,0,144,145,
        3,16,8,0,145,146,5,2,0,0,146,147,5,21,0,0,147,148,5,62,0,0,148,153,
        5,2,0,0,149,150,5,22,0,0,150,151,3,28,14,0,151,152,5,2,0,0,152,154,
        1,0,0,0,153,149,1,0,0,0,153,154,1,0,0,0,154,158,1,0,0,0,155,157,
        3,30,15,0,156,155,1,0,0,0,157,160,1,0,0,0,158,156,1,0,0,0,158,159,
        1,0,0,0,159,161,1,0,0,0,160,158,1,0,0,0,161,162,5,5,0,0,162,15,1,
        0,0,0,163,164,7,1,0,0,164,17,1,0,0,0,165,166,5,31,0,0,166,167,3,
        42,21,0,167,168,5,4,0,0,168,169,5,16,0,0,169,170,5,62,0,0,170,171,
        5,2,0,0,171,172,5,3,0,0,172,173,3,42,21,0,173,175,5,2,0,0,174,176,
        3,20,10,0,175,174,1,0,0,0,175,176,1,0,0,0,176,177,1,0,0,0,177,178,
        5,5,0,0,178,19,1,0,0,0,179,180,5,32,0,0,180,181,5,4,0,0,181,182,
        5,33,0,0,182,183,5,62,0,0,183,184,5,2,0,0,184,185,5,34,0,0,185,186,
        5,62,0,0,186,187,5,2,0,0,187,188,5,35,0,0,188,189,5,62,0,0,189,190,
        5,2,0,0,190,191,5,36,0,0,191,192,5,62,0,0,192,193,5,2,0,0,193,194,
        5,18,0,0,194,195,5,62,0,0,195,196,5,2,0,0,196,197,5,19,0,0,197,198,
        5,62,0,0,198,199,5,2,0,0,199,200,5,37,0,0,200,201,3,34,17,0,201,
        202,5,2,0,0,202,203,5,38,0,0,203,204,5,62,0,0,204,205,3,32,16,0,
        205,206,3,40,20,0,206,207,5,2,0,0,207,208,5,5,0,0,208,21,1,0,0,0,
        209,210,5,39,0,0,210,211,3,42,21,0,211,212,5,4,0,0,212,213,5,40,
        0,0,213,214,3,42,21,0,214,215,5,2,0,0,215,216,5,20,0,0,216,217,3,
        42,21,0,217,222,5,2,0,0,218,219,5,11,0,0,219,220,3,28,14,0,220,221,
        5,2,0,0,221,223,1,0,0,0,222,218,1,0,0,0,222,223,1,0,0,0,223,228,
        1,0,0,0,224,225,5,41,0,0,225,226,3,28,14,0,226,227,5,2,0,0,227,229,
        1,0,0,0,228,224,1,0,0,0,228,229,1,0,0,0,229,234,1,0,0,0,230,231,
        5,42,0,0,231,232,3,28,14,0,232,233,5,2,0,0,233,235,1,0,0,0,234,230,
        1,0,0,0,234,235,1,0,0,0,235,240,1,0,0,0,236,237,5,43,0,0,237,238,
        3,42,21,0,238,239,5,2,0,0,239,241,1,0,0,0,240,236,1,0,0,0,240,241,
        1,0,0,0,241,242,1,0,0,0,242,243,5,5,0,0,243,23,1,0,0,0,244,245,5,
        44,0,0,245,246,3,42,21,0,246,247,5,4,0,0,247,248,5,45,0,0,248,249,
        3,26,13,0,249,250,3,42,21,0,250,251,5,2,0,0,251,252,5,11,0,0,252,
        253,3,28,14,0,253,254,5,2,0,0,254,255,5,5,0,0,255,25,1,0,0,0,256,
        257,7,2,0,0,257,27,1,0,0,0,258,263,3,42,21,0,259,260,5,46,0,0,260,
        262,3,42,21,0,261,259,1,0,0,0,262,265,1,0,0,0,263,261,1,0,0,0,263,
        264,1,0,0,0,264,29,1,0,0,0,265,263,1,0,0,0,266,267,5,47,0,0,267,
        268,5,62,0,0,268,269,3,32,16,0,269,270,3,40,20,0,270,271,5,2,0,0,
        271,31,1,0,0,0,272,273,7,3,0,0,273,33,1,0,0,0,274,278,3,40,20,0,
        275,278,3,36,18,0,276,278,3,38,19,0,277,274,1,0,0,0,277,275,1,0,
        0,0,277,276,1,0,0,0,278,35,1,0,0,0,279,292,5,4,0,0,280,281,5,62,
        0,0,281,282,5,54,0,0,282,289,3,34,17,0,283,284,5,46,0,0,284,285,
        5,62,0,0,285,286,5,54,0,0,286,288,3,34,17,0,287,283,1,0,0,0,288,
        291,1,0,0,0,289,287,1,0,0,0,289,290,1,0,0,0,290,293,1,0,0,0,291,
        289,1,0,0,0,292,280,1,0,0,0,292,293,1,0,0,0,293,294,1,0,0,0,294,
        295,5,5,0,0,295,37,1,0,0,0,296,305,5,55,0,0,297,302,3,34,17,0,298,
        299,5,46,0,0,299,301,3,34,17,0,300,298,1,0,0,0,301,304,1,0,0,0,302,
        300,1,0,0,0,302,303,1,0,0,0,303,306,1,0,0,0,304,302,1,0,0,0,305,
        297,1,0,0,0,305,306,1,0,0,0,306,307,1,0,0,0,307,308,5,56,0,0,308,
        39,1,0,0,0,309,310,7,4,0,0,310,41,1,0,0,0,311,312,7,5,0,0,312,43,
        1,0,0,0,20,50,63,71,107,112,131,136,153,158,175,222,228,234,240,
        263,277,289,292,302,305
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
                     "'valid_from'", "'valid_until'", "'reasoning'", "'rationale'", 
                     "'backing'", "'structured'", "'deductive'", "'inductive'", 
                     "'abductive'", "'causal'", "'counterfactual'", "'analogical'", 
                     "'temporal'", "'claim'", "'proposition'", "'subject'", 
                     "'quantity'", "'unit'", "'scope'", "'query'", "'result'", 
                     "'argument'", "'conclusion'", "'assumptions'", "'premises'", 
                     "'binding'", "'objection'", "'target'", "','", "'require'", 
                     "'=='", "'!='", "'<='", "'>='", "'<'", "'>'", "':'", 
                     "'['", "']'", "'true'", "'false'", "'null'" ]

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
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "ID", "NUMBER", "STRING", "LINE_COMMENT", "BLOCK_COMMENT", 
                      "WS" ]

    RULE_program = 0
    RULE_declaration = 1
    RULE_environmentDecl = 2
    RULE_toolDecl = 3
    RULE_executionMode = 4
    RULE_evidenceDecl = 5
    RULE_assumptionDecl = 6
    RULE_reasoningDecl = 7
    RULE_reasoningMode = 8
    RULE_claimDecl = 9
    RULE_propositionDecl = 10
    RULE_argumentDecl = 11
    RULE_objectionDecl = 12
    RULE_targetKind = 13
    RULE_idList = 14
    RULE_predicate = 15
    RULE_comparator = 16
    RULE_jsonValue = 17
    RULE_jsonObject = 18
    RULE_jsonArray = 19
    RULE_jsonScalar = 20
    RULE_identifier = 21

    ruleNames =  [ "program", "declaration", "environmentDecl", "toolDecl", 
                   "executionMode", "evidenceDecl", "assumptionDecl", "reasoningDecl", 
                   "reasoningMode", "claimDecl", "propositionDecl", "argumentDecl", 
                   "objectionDecl", "targetKind", "idList", "predicate", 
                   "comparator", "jsonValue", "jsonObject", "jsonArray", 
                   "jsonScalar", "identifier" ]

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
    T__57=58
    T__58=59
    ID=60
    NUMBER=61
    STRING=62
    LINE_COMMENT=63
    BLOCK_COMMENT=64
    WS=65

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
            self.state = 44
            self.match(EALParser.T__0)
            self.state = 45
            self.match(EALParser.STRING)
            self.state = 46
            self.match(EALParser.T__1)
            self.state = 50
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 18144090425416) != 0):
                self.state = 47
                self.declaration()
                self.state = 52
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 53
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
            self.state = 63
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [3]:
                self.enterOuterAlt(localctx, 1)
                self.state = 55
                self.environmentDecl()
                pass
            elif token in [6]:
                self.enterOuterAlt(localctx, 2)
                self.state = 56
                self.toolDecl()
                pass
            elif token in [11]:
                self.enterOuterAlt(localctx, 3)
                self.state = 57
                self.evidenceDecl()
                pass
            elif token in [15]:
                self.enterOuterAlt(localctx, 4)
                self.state = 58
                self.assumptionDecl()
                pass
            elif token in [20]:
                self.enterOuterAlt(localctx, 5)
                self.state = 59
                self.reasoningDecl()
                pass
            elif token in [31]:
                self.enterOuterAlt(localctx, 6)
                self.state = 60
                self.claimDecl()
                pass
            elif token in [39]:
                self.enterOuterAlt(localctx, 7)
                self.state = 61
                self.argumentDecl()
                pass
            elif token in [44]:
                self.enterOuterAlt(localctx, 8)
                self.state = 62
                self.objectionDecl()
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
            self.state = 65
            self.match(EALParser.T__2)
            self.state = 66
            self.identifier()
            self.state = 67
            self.match(EALParser.T__3)
            self.state = 69 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 68
                self.predicate()
                self.state = 71 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==47):
                    break

            self.state = 73
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
            self.state = 75
            self.match(EALParser.T__5)
            self.state = 76
            self.identifier()
            self.state = 77
            self.match(EALParser.T__3)
            self.state = 78
            self.match(EALParser.T__6)
            self.state = 79
            self.match(EALParser.STRING)
            self.state = 80
            self.match(EALParser.T__1)
            self.state = 81
            self.match(EALParser.T__7)
            self.state = 82
            self.executionMode()
            self.state = 83
            self.match(EALParser.T__1)
            self.state = 84
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
            self.state = 86
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
            self.state = 88
            self.match(EALParser.T__10)
            self.state = 89
            self.identifier()
            self.state = 90
            self.match(EALParser.T__3)
            self.state = 91
            self.match(EALParser.T__5)
            self.state = 92
            self.identifier()
            self.state = 93
            self.match(EALParser.T__1)
            self.state = 94
            self.match(EALParser.T__11)
            self.state = 95
            self.identifier()
            self.state = 96
            self.match(EALParser.T__1)
            self.state = 97
            self.match(EALParser.T__2)
            self.state = 98
            self.identifier()
            self.state = 99
            self.match(EALParser.T__1)
            self.state = 100
            self.match(EALParser.T__12)
            self.state = 101
            self.match(EALParser.NUMBER)
            self.state = 102
            self.match(EALParser.T__1)
            self.state = 107
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==14:
                self.state = 103
                self.match(EALParser.T__13)
                self.state = 104
                self.jsonValue()
                self.state = 105
                self.match(EALParser.T__1)


            self.state = 110 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 109
                self.predicate()
                self.state = 112 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==47):
                    break

            self.state = 114
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
            self.state = 116
            self.match(EALParser.T__14)
            self.state = 117
            self.identifier()
            self.state = 118
            self.match(EALParser.T__3)
            self.state = 119
            self.match(EALParser.T__15)
            self.state = 120
            self.match(EALParser.STRING)
            self.state = 121
            self.match(EALParser.T__1)
            self.state = 122
            self.match(EALParser.T__2)
            self.state = 123
            self.identifier()
            self.state = 124
            self.match(EALParser.T__1)
            self.state = 125
            self.match(EALParser.T__16)
            self.state = 126
            self.identifier()
            self.state = 127
            self.match(EALParser.T__1)
            self.state = 131
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==18:
                self.state = 128
                self.match(EALParser.T__17)
                self.state = 129
                self.match(EALParser.STRING)
                self.state = 130
                self.match(EALParser.T__1)


            self.state = 136
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==19:
                self.state = 133
                self.match(EALParser.T__18)
                self.state = 134
                self.match(EALParser.STRING)
                self.state = 135
                self.match(EALParser.T__1)


            self.state = 138
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

        def identifier(self):
            return self.getTypedRuleContext(EALParser.IdentifierContext,0)


        def reasoningMode(self):
            return self.getTypedRuleContext(EALParser.ReasoningModeContext,0)


        def STRING(self):
            return self.getToken(EALParser.STRING, 0)

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
            self.state = 140
            self.match(EALParser.T__19)
            self.state = 141
            self.identifier()
            self.state = 142
            self.match(EALParser.T__3)
            self.state = 143
            self.match(EALParser.T__7)
            self.state = 144
            self.reasoningMode()
            self.state = 145
            self.match(EALParser.T__1)
            self.state = 146
            self.match(EALParser.T__20)
            self.state = 147
            self.match(EALParser.STRING)
            self.state = 148
            self.match(EALParser.T__1)
            self.state = 153
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==22:
                self.state = 149
                self.match(EALParser.T__21)
                self.state = 150
                self.idList()
                self.state = 151
                self.match(EALParser.T__1)


            self.state = 158
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==47:
                self.state = 155
                self.predicate()
                self.state = 160
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 161
            self.match(EALParser.T__4)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ReasoningModeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return EALParser.RULE_reasoningMode

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitReasoningMode" ):
                return visitor.visitReasoningMode(self)
            else:
                return visitor.visitChildren(self)




    def reasoningMode(self):

        localctx = EALParser.ReasoningModeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_reasoningMode)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 163
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 2139095040) != 0)):
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
        self.enterRule(localctx, 18, self.RULE_claimDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 165
            self.match(EALParser.T__30)
            self.state = 166
            self.identifier()
            self.state = 167
            self.match(EALParser.T__3)
            self.state = 168
            self.match(EALParser.T__15)
            self.state = 169
            self.match(EALParser.STRING)
            self.state = 170
            self.match(EALParser.T__1)
            self.state = 171
            self.match(EALParser.T__2)
            self.state = 172
            self.identifier()
            self.state = 173
            self.match(EALParser.T__1)
            self.state = 175
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==32:
                self.state = 174
                self.propositionDecl()


            self.state = 177
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
        self.enterRule(localctx, 20, self.RULE_propositionDecl)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 179
            self.match(EALParser.T__31)
            self.state = 180
            self.match(EALParser.T__3)
            self.state = 181
            self.match(EALParser.T__32)
            self.state = 182
            self.match(EALParser.STRING)
            self.state = 183
            self.match(EALParser.T__1)
            self.state = 184
            self.match(EALParser.T__33)
            self.state = 185
            self.match(EALParser.STRING)
            self.state = 186
            self.match(EALParser.T__1)
            self.state = 187
            self.match(EALParser.T__34)
            self.state = 188
            self.match(EALParser.STRING)
            self.state = 189
            self.match(EALParser.T__1)
            self.state = 190
            self.match(EALParser.T__35)
            self.state = 191
            self.match(EALParser.STRING)
            self.state = 192
            self.match(EALParser.T__1)
            self.state = 193
            self.match(EALParser.T__17)
            self.state = 194
            self.match(EALParser.STRING)
            self.state = 195
            self.match(EALParser.T__1)
            self.state = 196
            self.match(EALParser.T__18)
            self.state = 197
            self.match(EALParser.STRING)
            self.state = 198
            self.match(EALParser.T__1)
            self.state = 199
            self.match(EALParser.T__36)
            self.state = 200
            self.jsonValue()
            self.state = 201
            self.match(EALParser.T__1)
            self.state = 202
            self.match(EALParser.T__37)
            self.state = 203
            self.match(EALParser.STRING)
            self.state = 204
            self.comparator()
            self.state = 205
            self.jsonScalar()
            self.state = 206
            self.match(EALParser.T__1)
            self.state = 207
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
            self.evidenceRefs = None # IdListContext
            self.assumptionRefs = None # IdListContext
            self.premiseRefs = None # IdListContext

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
            return EALParser.RULE_argumentDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArgumentDecl" ):
                return visitor.visitArgumentDecl(self)
            else:
                return visitor.visitChildren(self)




    def argumentDecl(self):

        localctx = EALParser.ArgumentDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_argumentDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 209
            self.match(EALParser.T__38)
            self.state = 210
            self.identifier()
            self.state = 211
            self.match(EALParser.T__3)
            self.state = 212
            self.match(EALParser.T__39)
            self.state = 213
            self.identifier()
            self.state = 214
            self.match(EALParser.T__1)
            self.state = 215
            self.match(EALParser.T__19)
            self.state = 216
            self.identifier()
            self.state = 217
            self.match(EALParser.T__1)
            self.state = 222
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 218
                self.match(EALParser.T__10)
                self.state = 219
                localctx.evidenceRefs = self.idList()
                self.state = 220
                self.match(EALParser.T__1)


            self.state = 228
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==41:
                self.state = 224
                self.match(EALParser.T__40)
                self.state = 225
                localctx.assumptionRefs = self.idList()
                self.state = 226
                self.match(EALParser.T__1)


            self.state = 234
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==42:
                self.state = 230
                self.match(EALParser.T__41)
                self.state = 231
                localctx.premiseRefs = self.idList()
                self.state = 232
                self.match(EALParser.T__1)


            self.state = 240
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==43:
                self.state = 236
                self.match(EALParser.T__42)
                self.state = 237
                self.identifier()
                self.state = 238
                self.match(EALParser.T__1)


            self.state = 242
            self.match(EALParser.T__4)
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

        def identifier(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EALParser.IdentifierContext)
            else:
                return self.getTypedRuleContext(EALParser.IdentifierContext,i)


        def targetKind(self):
            return self.getTypedRuleContext(EALParser.TargetKindContext,0)


        def idList(self):
            return self.getTypedRuleContext(EALParser.IdListContext,0)


        def getRuleIndex(self):
            return EALParser.RULE_objectionDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitObjectionDecl" ):
                return visitor.visitObjectionDecl(self)
            else:
                return visitor.visitChildren(self)




    def objectionDecl(self):

        localctx = EALParser.ObjectionDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_objectionDecl)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 244
            self.match(EALParser.T__43)
            self.state = 245
            self.identifier()
            self.state = 246
            self.match(EALParser.T__3)
            self.state = 247
            self.match(EALParser.T__44)
            self.state = 248
            self.targetKind()
            self.state = 249
            self.identifier()
            self.state = 250
            self.match(EALParser.T__1)
            self.state = 251
            self.match(EALParser.T__10)
            self.state = 252
            self.idList()
            self.state = 253
            self.match(EALParser.T__1)
            self.state = 254
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
        self.enterRule(localctx, 26, self.RULE_targetKind)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 256
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 2148564992) != 0)):
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
        self.enterRule(localctx, 28, self.RULE_idList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 258
            self.identifier()
            self.state = 263
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==46:
                self.state = 259
                self.match(EALParser.T__45)
                self.state = 260
                self.identifier()
                self.state = 265
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
        self.enterRule(localctx, 30, self.RULE_predicate)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 266
            self.match(EALParser.T__46)
            self.state = 267
            self.match(EALParser.STRING)
            self.state = 268
            self.comparator()
            self.state = 269
            self.jsonScalar()
            self.state = 270
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
        self.enterRule(localctx, 32, self.RULE_comparator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 272
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 17732923532771328) != 0)):
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
        self.enterRule(localctx, 34, self.RULE_jsonValue)
        try:
            self.state = 277
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [57, 58, 59, 61, 62]:
                self.enterOuterAlt(localctx, 1)
                self.state = 274
                self.jsonScalar()
                pass
            elif token in [4]:
                self.enterOuterAlt(localctx, 2)
                self.state = 275
                self.jsonObject()
                pass
            elif token in [55]:
                self.enterOuterAlt(localctx, 3)
                self.state = 276
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
        self.enterRule(localctx, 36, self.RULE_jsonObject)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 279
            self.match(EALParser.T__3)
            self.state = 292
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==62:
                self.state = 280
                self.match(EALParser.STRING)
                self.state = 281
                self.match(EALParser.T__53)
                self.state = 282
                self.jsonValue()
                self.state = 289
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==46:
                    self.state = 283
                    self.match(EALParser.T__45)
                    self.state = 284
                    self.match(EALParser.STRING)
                    self.state = 285
                    self.match(EALParser.T__53)
                    self.state = 286
                    self.jsonValue()
                    self.state = 291
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 294
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
        self.enterRule(localctx, 38, self.RULE_jsonArray)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 296
            self.match(EALParser.T__54)
            self.state = 305
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 7962364141191036944) != 0):
                self.state = 297
                self.jsonValue()
                self.state = 302
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==46:
                    self.state = 298
                    self.match(EALParser.T__45)
                    self.state = 299
                    self.jsonValue()
                    self.state = 304
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 307
            self.match(EALParser.T__55)
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
        self.enterRule(localctx, 40, self.RULE_jsonScalar)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 309
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 7926335344172072960) != 0)):
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
        self.enterRule(localctx, 42, self.RULE_identifier)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 311
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 1152930846160715776) != 0)):
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





