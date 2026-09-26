# Generated from grammar/EAL.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .EALParser import EALParser
else:
    from EALParser import EALParser

# This class defines a complete generic visitor for a parse tree produced by EALParser.

class EALVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by EALParser#program.
    def visitProgram(self, ctx:EALParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#declaration.
    def visitDeclaration(self, ctx:EALParser.DeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#aspicDecl.
    def visitAspicDecl(self, ctx:EALParser.AspicDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#aspicDirective.
    def visitAspicDirective(self, ctx:EALParser.AspicDirectiveContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#aspicRankKind.
    def visitAspicRankKind(self, ctx:EALParser.AspicRankKindContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#environmentDecl.
    def visitEnvironmentDecl(self, ctx:EALParser.EnvironmentDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#toolDecl.
    def visitToolDecl(self, ctx:EALParser.ToolDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#evidenceDecl.
    def visitEvidenceDecl(self, ctx:EALParser.EvidenceDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#assumptionDecl.
    def visitAssumptionDecl(self, ctx:EALParser.AssumptionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#reasoningDecl.
    def visitReasoningDecl(self, ctx:EALParser.ReasoningDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#claimDecl.
    def visitClaimDecl(self, ctx:EALParser.ClaimDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#propositionDecl.
    def visitPropositionDecl(self, ctx:EALParser.PropositionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#argumentDecl.
    def visitArgumentDecl(self, ctx:EALParser.ArgumentDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#argumentBody.
    def visitArgumentBody(self, ctx:EALParser.ArgumentBodyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#patternDecl.
    def visitPatternDecl(self, ctx:EALParser.PatternDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#patternParameter.
    def visitPatternParameter(self, ctx:EALParser.PatternParameterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#parameterKind.
    def visitParameterKind(self, ctx:EALParser.ParameterKindContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#applicationDecl.
    def visitApplicationDecl(self, ctx:EALParser.ApplicationDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#patternBinding.
    def visitPatternBinding(self, ctx:EALParser.PatternBindingContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#objectionDecl.
    def visitObjectionDecl(self, ctx:EALParser.ObjectionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#targetKind.
    def visitTargetKind(self, ctx:EALParser.TargetKindContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#idList.
    def visitIdList(self, ctx:EALParser.IdListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#predicate.
    def visitPredicate(self, ctx:EALParser.PredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#comparator.
    def visitComparator(self, ctx:EALParser.ComparatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#jsonValue.
    def visitJsonValue(self, ctx:EALParser.JsonValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#jsonObject.
    def visitJsonObject(self, ctx:EALParser.JsonObjectContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#jsonArray.
    def visitJsonArray(self, ctx:EALParser.JsonArrayContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#jsonScalar.
    def visitJsonScalar(self, ctx:EALParser.JsonScalarContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#identifier.
    def visitIdentifier(self, ctx:EALParser.IdentifierContext):
        return self.visitChildren(ctx)



del EALParser