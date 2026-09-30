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


    # Visit a parse tree produced by EALParser#contextDecl.
    def visitContextDecl(self, ctx:EALParser.ContextDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#contextAttribute.
    def visitContextAttribute(self, ctx:EALParser.ContextAttributeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#environmentDecl.
    def visitEnvironmentDecl(self, ctx:EALParser.EnvironmentDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#toolDecl.
    def visitToolDecl(self, ctx:EALParser.ToolDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#versionField.
    def visitVersionField(self, ctx:EALParser.VersionFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#evidenceDecl.
    def visitEvidenceDecl(self, ctx:EALParser.EvidenceDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#evidenceField.
    def visitEvidenceField(self, ctx:EALParser.EvidenceFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#toolField.
    def visitToolField(self, ctx:EALParser.ToolFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#kindField.
    def visitKindField(self, ctx:EALParser.KindFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#environmentField.
    def visitEnvironmentField(self, ctx:EALParser.EnvironmentFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#maxAgeField.
    def visitMaxAgeField(self, ctx:EALParser.MaxAgeFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#inputField.
    def visitInputField(self, ctx:EALParser.InputFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#assumptionDecl.
    def visitAssumptionDecl(self, ctx:EALParser.AssumptionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#assumptionField.
    def visitAssumptionField(self, ctx:EALParser.AssumptionFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#statementField.
    def visitStatementField(self, ctx:EALParser.StatementFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#validateField.
    def visitValidateField(self, ctx:EALParser.ValidateFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#validFromField.
    def visitValidFromField(self, ctx:EALParser.ValidFromFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#validUntilField.
    def visitValidUntilField(self, ctx:EALParser.ValidUntilFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#reasoningDecl.
    def visitReasoningDecl(self, ctx:EALParser.ReasoningDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#reasoningField.
    def visitReasoningField(self, ctx:EALParser.ReasoningFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#methodField.
    def visitMethodField(self, ctx:EALParser.MethodFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#rationaleField.
    def visitRationaleField(self, ctx:EALParser.RationaleFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#backingField.
    def visitBackingField(self, ctx:EALParser.BackingFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#claimDecl.
    def visitClaimDecl(self, ctx:EALParser.ClaimDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#claimField.
    def visitClaimField(self, ctx:EALParser.ClaimFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#propositionDecl.
    def visitPropositionDecl(self, ctx:EALParser.PropositionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#propositionField.
    def visitPropositionField(self, ctx:EALParser.PropositionFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#subjectField.
    def visitSubjectField(self, ctx:EALParser.SubjectFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#quantityField.
    def visitQuantityField(self, ctx:EALParser.QuantityFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#unitField.
    def visitUnitField(self, ctx:EALParser.UnitFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#scopeField.
    def visitScopeField(self, ctx:EALParser.ScopeFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#queryField.
    def visitQueryField(self, ctx:EALParser.QueryFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#resultField.
    def visitResultField(self, ctx:EALParser.ResultFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#argumentDecl.
    def visitArgumentDecl(self, ctx:EALParser.ArgumentDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#argumentFlow.
    def visitArgumentFlow(self, ctx:EALParser.ArgumentFlowContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#support.
    def visitSupport(self, ctx:EALParser.SupportContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#supportGroup.
    def visitSupportGroup(self, ctx:EALParser.SupportGroupContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#supportKind.
    def visitSupportKind(self, ctx:EALParser.SupportKindContext):
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


    # Visit a parse tree produced by EALParser#objectionSupport.
    def visitObjectionSupport(self, ctx:EALParser.ObjectionSupportContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#objectionGroup.
    def visitObjectionGroup(self, ctx:EALParser.ObjectionGroupContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#objectionSupportKind.
    def visitObjectionSupportKind(self, ctx:EALParser.ObjectionSupportKindContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#targetKind.
    def visitTargetKind(self, ctx:EALParser.TargetKindContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#argumentationDirective.
    def visitArgumentationDirective(self, ctx:EALParser.ArgumentationDirectiveContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#referenceList.
    def visitReferenceList(self, ctx:EALParser.ReferenceListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#predicate.
    def visitPredicate(self, ctx:EALParser.PredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EALParser#key.
    def visitKey(self, ctx:EALParser.KeyContext):
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


    # Visit a parse tree produced by EALParser#lineEnd.
    def visitLineEnd(self, ctx:EALParser.LineEndContext):
        return self.visitChildren(ctx)



del EALParser
