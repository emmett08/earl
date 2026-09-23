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
        4,1,57,269,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,1,0,
        1,0,1,0,1,0,5,0,45,8,0,10,0,12,0,48,9,0,1,0,1,0,1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,3,1,60,8,1,1,2,1,2,1,2,1,2,4,2,66,8,2,11,2,12,2,
        67,1,2,1,2,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,4,1,4,1,
        5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,
        5,1,5,1,5,3,5,104,8,5,1,5,4,5,107,8,5,11,5,12,5,108,1,5,1,5,1,6,
        1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,1,6,3,6,128,
        8,6,1,6,1,6,1,6,3,6,133,8,6,1,6,1,6,1,7,1,7,1,7,1,7,1,7,1,7,1,7,
        1,7,1,7,1,7,1,7,1,7,1,7,3,7,150,8,7,1,7,5,7,153,8,7,10,7,12,7,156,
        9,7,1,7,1,7,1,8,1,8,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,
        1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,
        3,10,186,8,10,1,10,1,10,1,10,1,10,3,10,192,8,10,1,10,1,10,1,10,1,
        10,3,10,198,8,10,1,10,1,10,1,11,1,11,1,11,1,11,1,11,1,11,1,11,1,
        11,1,11,1,11,1,11,1,11,1,12,1,12,1,13,1,13,1,13,5,13,219,8,13,10,
        13,12,13,222,9,13,1,14,1,14,1,14,1,14,1,14,1,14,1,15,1,15,1,16,1,
        16,1,16,3,16,235,8,16,1,17,1,17,1,17,1,17,1,17,1,17,1,17,1,17,5,
        17,245,8,17,10,17,12,17,248,9,17,3,17,250,8,17,1,17,1,17,1,18,1,
        18,1,18,1,18,5,18,258,8,18,10,18,12,18,261,9,18,3,18,263,8,18,1,
        18,1,18,1,19,1,19,1,19,0,0,20,0,2,4,6,8,10,12,14,16,18,20,22,24,
        26,28,30,32,34,36,38,0,5,1,0,9,10,1,0,23,30,3,0,15,15,20,20,31,31,
        1,0,40,45,2,0,49,51,53,54,273,0,40,1,0,0,0,2,59,1,0,0,0,4,61,1,0,
        0,0,6,71,1,0,0,0,8,82,1,0,0,0,10,84,1,0,0,0,12,112,1,0,0,0,14,136,
        1,0,0,0,16,159,1,0,0,0,18,161,1,0,0,0,20,172,1,0,0,0,22,201,1,0,
        0,0,24,213,1,0,0,0,26,215,1,0,0,0,28,223,1,0,0,0,30,229,1,0,0,0,
        32,234,1,0,0,0,34,236,1,0,0,0,36,253,1,0,0,0,38,266,1,0,0,0,40,41,
        5,1,0,0,41,42,5,54,0,0,42,46,5,2,0,0,43,45,3,2,1,0,44,43,1,0,0,0,
        45,48,1,0,0,0,46,44,1,0,0,0,46,47,1,0,0,0,47,49,1,0,0,0,48,46,1,
        0,0,0,49,50,5,0,0,1,50,1,1,0,0,0,51,60,3,4,2,0,52,60,3,6,3,0,53,
        60,3,10,5,0,54,60,3,12,6,0,55,60,3,14,7,0,56,60,3,18,9,0,57,60,3,
        20,10,0,58,60,3,22,11,0,59,51,1,0,0,0,59,52,1,0,0,0,59,53,1,0,0,
        0,59,54,1,0,0,0,59,55,1,0,0,0,59,56,1,0,0,0,59,57,1,0,0,0,59,58,
        1,0,0,0,60,3,1,0,0,0,61,62,5,3,0,0,62,63,5,52,0,0,63,65,5,4,0,0,
        64,66,3,28,14,0,65,64,1,0,0,0,66,67,1,0,0,0,67,65,1,0,0,0,67,68,
        1,0,0,0,68,69,1,0,0,0,69,70,5,5,0,0,70,5,1,0,0,0,71,72,5,6,0,0,72,
        73,5,52,0,0,73,74,5,4,0,0,74,75,5,7,0,0,75,76,5,54,0,0,76,77,5,2,
        0,0,77,78,5,8,0,0,78,79,3,8,4,0,79,80,5,2,0,0,80,81,5,5,0,0,81,7,
        1,0,0,0,82,83,7,0,0,0,83,9,1,0,0,0,84,85,5,11,0,0,85,86,5,52,0,0,
        86,87,5,4,0,0,87,88,5,6,0,0,88,89,5,52,0,0,89,90,5,2,0,0,90,91,5,
        12,0,0,91,92,5,52,0,0,92,93,5,2,0,0,93,94,5,3,0,0,94,95,5,52,0,0,
        95,96,5,2,0,0,96,97,5,13,0,0,97,98,5,53,0,0,98,103,5,2,0,0,99,100,
        5,14,0,0,100,101,3,32,16,0,101,102,5,2,0,0,102,104,1,0,0,0,103,99,
        1,0,0,0,103,104,1,0,0,0,104,106,1,0,0,0,105,107,3,28,14,0,106,105,
        1,0,0,0,107,108,1,0,0,0,108,106,1,0,0,0,108,109,1,0,0,0,109,110,
        1,0,0,0,110,111,5,5,0,0,111,11,1,0,0,0,112,113,5,15,0,0,113,114,
        5,52,0,0,114,115,5,4,0,0,115,116,5,16,0,0,116,117,5,54,0,0,117,118,
        5,2,0,0,118,119,5,3,0,0,119,120,5,52,0,0,120,121,5,2,0,0,121,122,
        5,17,0,0,122,123,5,52,0,0,123,127,5,2,0,0,124,125,5,18,0,0,125,126,
        5,54,0,0,126,128,5,2,0,0,127,124,1,0,0,0,127,128,1,0,0,0,128,132,
        1,0,0,0,129,130,5,19,0,0,130,131,5,54,0,0,131,133,5,2,0,0,132,129,
        1,0,0,0,132,133,1,0,0,0,133,134,1,0,0,0,134,135,5,5,0,0,135,13,1,
        0,0,0,136,137,5,20,0,0,137,138,5,52,0,0,138,139,5,4,0,0,139,140,
        5,8,0,0,140,141,3,16,8,0,141,142,5,2,0,0,142,143,5,21,0,0,143,144,
        5,54,0,0,144,149,5,2,0,0,145,146,5,22,0,0,146,147,3,26,13,0,147,
        148,5,2,0,0,148,150,1,0,0,0,149,145,1,0,0,0,149,150,1,0,0,0,150,
        154,1,0,0,0,151,153,3,28,14,0,152,151,1,0,0,0,153,156,1,0,0,0,154,
        152,1,0,0,0,154,155,1,0,0,0,155,157,1,0,0,0,156,154,1,0,0,0,157,
        158,5,5,0,0,158,15,1,0,0,0,159,160,7,1,0,0,160,17,1,0,0,0,161,162,
        5,31,0,0,162,163,5,52,0,0,163,164,5,4,0,0,164,165,5,16,0,0,165,166,
        5,54,0,0,166,167,5,2,0,0,167,168,5,3,0,0,168,169,5,52,0,0,169,170,
        5,2,0,0,170,171,5,5,0,0,171,19,1,0,0,0,172,173,5,32,0,0,173,174,
        5,52,0,0,174,175,5,4,0,0,175,176,5,33,0,0,176,177,5,52,0,0,177,178,
        5,2,0,0,178,179,5,20,0,0,179,180,5,52,0,0,180,185,5,2,0,0,181,182,
        5,11,0,0,182,183,3,26,13,0,183,184,5,2,0,0,184,186,1,0,0,0,185,181,
        1,0,0,0,185,186,1,0,0,0,186,191,1,0,0,0,187,188,5,34,0,0,188,189,
        3,26,13,0,189,190,5,2,0,0,190,192,1,0,0,0,191,187,1,0,0,0,191,192,
        1,0,0,0,192,197,1,0,0,0,193,194,5,35,0,0,194,195,3,26,13,0,195,196,
        5,2,0,0,196,198,1,0,0,0,197,193,1,0,0,0,197,198,1,0,0,0,198,199,
        1,0,0,0,199,200,5,5,0,0,200,21,1,0,0,0,201,202,5,36,0,0,202,203,
        5,52,0,0,203,204,5,4,0,0,204,205,5,37,0,0,205,206,3,24,12,0,206,
        207,5,52,0,0,207,208,5,2,0,0,208,209,5,11,0,0,209,210,3,26,13,0,
        210,211,5,2,0,0,211,212,5,5,0,0,212,23,1,0,0,0,213,214,7,2,0,0,214,
        25,1,0,0,0,215,220,5,52,0,0,216,217,5,38,0,0,217,219,5,52,0,0,218,
        216,1,0,0,0,219,222,1,0,0,0,220,218,1,0,0,0,220,221,1,0,0,0,221,
        27,1,0,0,0,222,220,1,0,0,0,223,224,5,39,0,0,224,225,5,54,0,0,225,
        226,3,30,15,0,226,227,3,38,19,0,227,228,5,2,0,0,228,29,1,0,0,0,229,
        230,7,3,0,0,230,31,1,0,0,0,231,235,3,38,19,0,232,235,3,34,17,0,233,
        235,3,36,18,0,234,231,1,0,0,0,234,232,1,0,0,0,234,233,1,0,0,0,235,
        33,1,0,0,0,236,249,5,4,0,0,237,238,5,54,0,0,238,239,5,46,0,0,239,
        246,3,32,16,0,240,241,5,38,0,0,241,242,5,54,0,0,242,243,5,46,0,0,
        243,245,3,32,16,0,244,240,1,0,0,0,245,248,1,0,0,0,246,244,1,0,0,
        0,246,247,1,0,0,0,247,250,1,0,0,0,248,246,1,0,0,0,249,237,1,0,0,
        0,249,250,1,0,0,0,250,251,1,0,0,0,251,252,5,5,0,0,252,35,1,0,0,0,
        253,262,5,47,0,0,254,259,3,32,16,0,255,256,5,38,0,0,256,258,3,32,
        16,0,257,255,1,0,0,0,258,261,1,0,0,0,259,257,1,0,0,0,259,260,1,0,
        0,0,260,263,1,0,0,0,261,259,1,0,0,0,262,254,1,0,0,0,262,263,1,0,
        0,0,263,264,1,0,0,0,264,265,5,48,0,0,265,37,1,0,0,0,266,267,7,4,
        0,0,267,39,1,0,0,0,18,46,59,67,103,108,127,132,149,154,185,191,197,
        220,234,246,249,259,262
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
                     "'temporal'", "'claim'", "'argument'", "'conclusion'", 
                     "'assumptions'", "'premises'", "'objection'", "'target'", 
                     "','", "'require'", "'=='", "'!='", "'<='", "'>='", 
                     "'<'", "'>'", "':'", "'['", "']'", "'true'", "'false'", 
                     "'null'" ]

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
    RULE_argumentDecl = 10
    RULE_objectionDecl = 11
    RULE_targetKind = 12
    RULE_idList = 13
    RULE_predicate = 14
    RULE_comparator = 15
    RULE_jsonValue = 16
    RULE_jsonObject = 17
    RULE_jsonArray = 18
    RULE_jsonScalar = 19

    ruleNames =  [ "program", "declaration", "environmentDecl", "toolDecl", 
                   "executionMode", "evidenceDecl", "assumptionDecl", "reasoningDecl", 
                   "reasoningMode", "claimDecl", "argumentDecl", "objectionDecl", 
                   "targetKind", "idList", "predicate", "comparator", "jsonValue", 
                   "jsonObject", "jsonArray", "jsonScalar" ]

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
    ID=52
    NUMBER=53
    STRING=54
    LINE_COMMENT=55
    BLOCK_COMMENT=56
    WS=57

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
            self.state = 40
            self.match(EALParser.T__0)
            self.state = 41
            self.match(EALParser.STRING)
            self.state = 42
            self.match(EALParser.T__1)
            self.state = 46
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 75163011144) != 0):
                self.state = 43
                self.declaration()
                self.state = 48
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 49
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
            self.state = 59
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [3]:
                self.enterOuterAlt(localctx, 1)
                self.state = 51
                self.environmentDecl()
                pass
            elif token in [6]:
                self.enterOuterAlt(localctx, 2)
                self.state = 52
                self.toolDecl()
                pass
            elif token in [11]:
                self.enterOuterAlt(localctx, 3)
                self.state = 53
                self.evidenceDecl()
                pass
            elif token in [15]:
                self.enterOuterAlt(localctx, 4)
                self.state = 54
                self.assumptionDecl()
                pass
            elif token in [20]:
                self.enterOuterAlt(localctx, 5)
                self.state = 55
                self.reasoningDecl()
                pass
            elif token in [31]:
                self.enterOuterAlt(localctx, 6)
                self.state = 56
                self.claimDecl()
                pass
            elif token in [32]:
                self.enterOuterAlt(localctx, 7)
                self.state = 57
                self.argumentDecl()
                pass
            elif token in [36]:
                self.enterOuterAlt(localctx, 8)
                self.state = 58
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

        def ID(self):
            return self.getToken(EALParser.ID, 0)

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
            self.state = 61
            self.match(EALParser.T__2)
            self.state = 62
            self.match(EALParser.ID)
            self.state = 63
            self.match(EALParser.T__3)
            self.state = 65 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 64
                self.predicate()
                self.state = 67 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==39):
                    break

            self.state = 69
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

        def ID(self):
            return self.getToken(EALParser.ID, 0)

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
            self.state = 71
            self.match(EALParser.T__5)
            self.state = 72
            self.match(EALParser.ID)
            self.state = 73
            self.match(EALParser.T__3)
            self.state = 74
            self.match(EALParser.T__6)
            self.state = 75
            self.match(EALParser.STRING)
            self.state = 76
            self.match(EALParser.T__1)
            self.state = 77
            self.match(EALParser.T__7)
            self.state = 78
            self.executionMode()
            self.state = 79
            self.match(EALParser.T__1)
            self.state = 80
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
            self.state = 82
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

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.ID)
            else:
                return self.getToken(EALParser.ID, i)

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
            self.state = 84
            self.match(EALParser.T__10)
            self.state = 85
            self.match(EALParser.ID)
            self.state = 86
            self.match(EALParser.T__3)
            self.state = 87
            self.match(EALParser.T__5)
            self.state = 88
            self.match(EALParser.ID)
            self.state = 89
            self.match(EALParser.T__1)
            self.state = 90
            self.match(EALParser.T__11)
            self.state = 91
            self.match(EALParser.ID)
            self.state = 92
            self.match(EALParser.T__1)
            self.state = 93
            self.match(EALParser.T__2)
            self.state = 94
            self.match(EALParser.ID)
            self.state = 95
            self.match(EALParser.T__1)
            self.state = 96
            self.match(EALParser.T__12)
            self.state = 97
            self.match(EALParser.NUMBER)
            self.state = 98
            self.match(EALParser.T__1)
            self.state = 103
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==14:
                self.state = 99
                self.match(EALParser.T__13)
                self.state = 100
                self.jsonValue()
                self.state = 101
                self.match(EALParser.T__1)


            self.state = 106 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 105
                self.predicate()
                self.state = 108 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==39):
                    break

            self.state = 110
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

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.ID)
            else:
                return self.getToken(EALParser.ID, i)

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
            self.state = 112
            self.match(EALParser.T__14)
            self.state = 113
            self.match(EALParser.ID)
            self.state = 114
            self.match(EALParser.T__3)
            self.state = 115
            self.match(EALParser.T__15)
            self.state = 116
            self.match(EALParser.STRING)
            self.state = 117
            self.match(EALParser.T__1)
            self.state = 118
            self.match(EALParser.T__2)
            self.state = 119
            self.match(EALParser.ID)
            self.state = 120
            self.match(EALParser.T__1)
            self.state = 121
            self.match(EALParser.T__16)
            self.state = 122
            self.match(EALParser.ID)
            self.state = 123
            self.match(EALParser.T__1)
            self.state = 127
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==18:
                self.state = 124
                self.match(EALParser.T__17)
                self.state = 125
                self.match(EALParser.STRING)
                self.state = 126
                self.match(EALParser.T__1)


            self.state = 132
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==19:
                self.state = 129
                self.match(EALParser.T__18)
                self.state = 130
                self.match(EALParser.STRING)
                self.state = 131
                self.match(EALParser.T__1)


            self.state = 134
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

        def ID(self):
            return self.getToken(EALParser.ID, 0)

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
            self.state = 136
            self.match(EALParser.T__19)
            self.state = 137
            self.match(EALParser.ID)
            self.state = 138
            self.match(EALParser.T__3)
            self.state = 139
            self.match(EALParser.T__7)
            self.state = 140
            self.reasoningMode()
            self.state = 141
            self.match(EALParser.T__1)
            self.state = 142
            self.match(EALParser.T__20)
            self.state = 143
            self.match(EALParser.STRING)
            self.state = 144
            self.match(EALParser.T__1)
            self.state = 149
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==22:
                self.state = 145
                self.match(EALParser.T__21)
                self.state = 146
                self.idList()
                self.state = 147
                self.match(EALParser.T__1)


            self.state = 154
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==39:
                self.state = 151
                self.predicate()
                self.state = 156
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 157
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
            self.state = 159
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

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.ID)
            else:
                return self.getToken(EALParser.ID, i)

        def STRING(self):
            return self.getToken(EALParser.STRING, 0)

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
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 161
            self.match(EALParser.T__30)
            self.state = 162
            self.match(EALParser.ID)
            self.state = 163
            self.match(EALParser.T__3)
            self.state = 164
            self.match(EALParser.T__15)
            self.state = 165
            self.match(EALParser.STRING)
            self.state = 166
            self.match(EALParser.T__1)
            self.state = 167
            self.match(EALParser.T__2)
            self.state = 168
            self.match(EALParser.ID)
            self.state = 169
            self.match(EALParser.T__1)
            self.state = 170
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

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.ID)
            else:
                return self.getToken(EALParser.ID, i)

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
        self.enterRule(localctx, 20, self.RULE_argumentDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 172
            self.match(EALParser.T__31)
            self.state = 173
            self.match(EALParser.ID)
            self.state = 174
            self.match(EALParser.T__3)
            self.state = 175
            self.match(EALParser.T__32)
            self.state = 176
            self.match(EALParser.ID)
            self.state = 177
            self.match(EALParser.T__1)
            self.state = 178
            self.match(EALParser.T__19)
            self.state = 179
            self.match(EALParser.ID)
            self.state = 180
            self.match(EALParser.T__1)
            self.state = 185
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 181
                self.match(EALParser.T__10)
                self.state = 182
                localctx.evidenceRefs = self.idList()
                self.state = 183
                self.match(EALParser.T__1)


            self.state = 191
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==34:
                self.state = 187
                self.match(EALParser.T__33)
                self.state = 188
                localctx.assumptionRefs = self.idList()
                self.state = 189
                self.match(EALParser.T__1)


            self.state = 197
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==35:
                self.state = 193
                self.match(EALParser.T__34)
                self.state = 194
                localctx.premiseRefs = self.idList()
                self.state = 195
                self.match(EALParser.T__1)


            self.state = 199
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

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.ID)
            else:
                return self.getToken(EALParser.ID, i)

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
        self.enterRule(localctx, 22, self.RULE_objectionDecl)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 201
            self.match(EALParser.T__35)
            self.state = 202
            self.match(EALParser.ID)
            self.state = 203
            self.match(EALParser.T__3)
            self.state = 204
            self.match(EALParser.T__36)
            self.state = 205
            self.targetKind()
            self.state = 206
            self.match(EALParser.ID)
            self.state = 207
            self.match(EALParser.T__1)
            self.state = 208
            self.match(EALParser.T__10)
            self.state = 209
            self.idList()
            self.state = 210
            self.match(EALParser.T__1)
            self.state = 211
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
        self.enterRule(localctx, 24, self.RULE_targetKind)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 213
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

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EALParser.ID)
            else:
                return self.getToken(EALParser.ID, i)

        def getRuleIndex(self):
            return EALParser.RULE_idList

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIdList" ):
                return visitor.visitIdList(self)
            else:
                return visitor.visitChildren(self)




    def idList(self):

        localctx = EALParser.IdListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_idList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 215
            self.match(EALParser.ID)
            self.state = 220
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==38:
                self.state = 216
                self.match(EALParser.T__37)
                self.state = 217
                self.match(EALParser.ID)
                self.state = 222
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
        self.enterRule(localctx, 28, self.RULE_predicate)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 223
            self.match(EALParser.T__38)
            self.state = 224
            self.match(EALParser.STRING)
            self.state = 225
            self.comparator()
            self.state = 226
            self.jsonScalar()
            self.state = 227
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
        self.enterRule(localctx, 30, self.RULE_comparator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 229
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 69269232549888) != 0)):
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
        self.enterRule(localctx, 32, self.RULE_jsonValue)
        try:
            self.state = 234
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [49, 50, 51, 53, 54]:
                self.enterOuterAlt(localctx, 1)
                self.state = 231
                self.jsonScalar()
                pass
            elif token in [4]:
                self.enterOuterAlt(localctx, 2)
                self.state = 232
                self.jsonObject()
                pass
            elif token in [47]:
                self.enterOuterAlt(localctx, 3)
                self.state = 233
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
        self.enterRule(localctx, 34, self.RULE_jsonObject)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 236
            self.match(EALParser.T__3)
            self.state = 249
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==54:
                self.state = 237
                self.match(EALParser.STRING)
                self.state = 238
                self.match(EALParser.T__45)
                self.state = 239
                self.jsonValue()
                self.state = 246
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==38:
                    self.state = 240
                    self.match(EALParser.T__37)
                    self.state = 241
                    self.match(EALParser.STRING)
                    self.state = 242
                    self.match(EALParser.T__45)
                    self.state = 243
                    self.jsonValue()
                    self.state = 248
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 251
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
        self.enterRule(localctx, 36, self.RULE_jsonArray)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 253
            self.match(EALParser.T__46)
            self.state = 262
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 31102984926527504) != 0):
                self.state = 254
                self.jsonValue()
                self.state = 259
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==38:
                    self.state = 255
                    self.match(EALParser.T__37)
                    self.state = 256
                    self.jsonValue()
                    self.state = 261
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 264
            self.match(EALParser.T__47)
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
        self.enterRule(localctx, 38, self.RULE_jsonScalar)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 266
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 30962247438172160) != 0)):
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





