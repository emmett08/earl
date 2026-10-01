grammar EAL;

// EAL/3. Recognition is independent of binding, lowering and evaluation.
program : NL* 'language' STRING lineEnd (declaration NL*)* EOF ;
declaration
    : contextDecl | moduleDecl | importDecl | environmentDecl | toolDecl
    | evidenceDecl | assumptionDecl | reasoningDecl | claimDecl | argumentDecl
    | objectionDecl | patternDecl | applicationDecl | patternGuard
    | argumentationDirective
    ;
moduleDecl : 'module' qualifiedName '{' NL* (declaration NL*)* '}' ;
importDecl : 'import' STRING 'as' identifier lineEnd ;
contextDecl
    : 'context' contextAttribute (',' contextAttribute)*
      '{' NL* (declaration NL*)* '}'
    ;
contextAttribute
    : 'environment' qualifiedName | 'tool' qualifiedName | 'max_age' signedNumber
    | 'kind' identifier | 'input' jsonValue | 'version' STRING
    | 'validate' qualifiedName | 'method' STRING
    | 'subject' STRING | 'quantity' STRING | 'unit' STRING | 'scope' STRING
    | 'valid_from' STRING | 'valid_until' STRING | 'query' jsonValue
    ;
environmentDecl : 'environment' qualifiedName '{' NL* predicate+ '}' ;
toolDecl : 'tool' qualifiedName '{' NL* versionField* '}' ;
versionField : 'version' STRING lineEnd ;
evidenceDecl : 'evidence' qualifiedName '{' NL* evidenceField* '}' ;
evidenceField
    : toolField | kindField | environmentField | maxAgeField | inputField | predicate
    ;
toolField : 'tool' qualifiedName lineEnd ;
kindField : 'kind' identifier lineEnd ;
environmentField : 'environment' qualifiedName lineEnd ;
maxAgeField : 'max_age' signedNumber lineEnd ;
inputField : 'input' jsonValue lineEnd ;
assumptionDecl : 'assumption' qualifiedName '{' NL* assumptionField* '}' ;
assumptionField
    : statementField | environmentField | validateField | validFromField | validUntilField
    ;
statementField : 'statement' STRING lineEnd ;
validateField : 'validate' qualifiedName lineEnd ;
validFromField : 'valid_from' STRING lineEnd ;
validUntilField : 'valid_until' STRING lineEnd ;
reasoningDecl : 'reasoning' qualifiedName '{' NL* reasoningField* '}' ;
reasoningField : methodField | rationaleField | backingField | transferField | predicate ;
methodField : 'method' STRING lineEnd ;
rationaleField : 'rationale' STRING lineEnd ;
backingField : 'backing' referenceList lineEnd ;
transferField
    : 'transfer' 'from' qualifiedName 'to' qualifiedName
      'assuming' qualifiedName 'reviewed' STRING lineEnd
    ;
claimDecl : 'claim' qualifiedName '{' NL* claimField* '}' ;
claimField : statementField | environmentField | propositionDecl ;
propositionDecl : 'proposition' '{' NL* propositionField* '}' NL* ;
propositionField
    : subjectField | quantityField | unitField | scopeField | validFromField
    | validUntilField | queryField | resultField
    ;
subjectField : 'subject' STRING lineEnd ;
quantityField : 'quantity' STRING lineEnd ;
unitField : 'unit' STRING lineEnd ;
scopeField : 'scope' STRING lineEnd ;
queryField : 'query' jsonValue lineEnd ;
resultField : 'result' expression lineEnd ;
argumentDecl
    : 'argument' qualifiedName
      ('=' NL* argumentFlow lineEnd
      | '{' NL* (declaration NL*)* argumentFlow lineEnd '}')
    ;
argumentFlow
    : support NL* 'via' NL* reasoningRef=reference
      NL* '=>' NL* conclusionRef=reference
      (NL* 'binding' bindingRef=reference)?
    ;
support : '[' NL* (supportGroup (',' NL* supportGroup)*)? NL* ']' ;
supportGroup : supportKind reference (',' NL* reference)* ;
supportKind : 'evidence' | 'assumptions' | 'premises' ;
patternDecl
    : 'pattern' qualifiedName '(' NL*
      (patternParameter (',' NL* patternParameter)*)? NL* ')'
      (NL* 'decreases' identifier)? NL*
      ('=' NL* argumentFlow lineEnd | '{' NL* (declaration NL*)+ '}')
    ;
patternParameter : identifier ':' parameterKind ('[' ']')? ;
parameterKind : 'claim' | 'reasoning' | 'evidence' | 'assumption' | 'environment' | 'tool' | identifier ;
applicationDecl
    : 'apply' qualifiedName '=' qualifiedName '(' NL*
      (patternBinding (',' NL* patternBinding)*)? NL* ')' lineEnd
    ;
patternBinding : identifier '=' bindingValue ;
bindingValue : reference | '[' NL* (reference (',' NL* reference)*)? NL* ']' ;
patternGuard
    : 'when' identifier '{' NL* (declaration NL*)* '}'
      (NL* 'else' '{' NL* (declaration NL*)* '}')?
    ;
objectionDecl
    : 'objection' qualifiedName '=' NL* objectionSupport NL* '-x>' NL*
      targetKind reference lineEnd
    ;
objectionSupport : '[' NL* (objectionGroup (',' NL* objectionGroup)*)? NL* ']' ;
objectionGroup : objectionSupportKind reference (',' NL* reference)* ;
objectionSupportKind : 'evidence' | 'premises' ;
targetKind : 'claim' | 'reasoning' | 'assumption' | 'argument' | 'objection' ;
argumentationDirective
    : 'strict' qualifiedName 'reviewed' STRING lineEnd
    | 'rank' qualifiedName signedNumber 'reviewed' STRING lineEnd
    | 'contrary' qualifiedName 'to' qualifiedName 'reviewed' STRING lineEnd
    | 'prefer' qualifiedName 'over' qualifiedName 'reviewed' STRING lineEnd
    ;
referenceList : '[' NL* reference (',' NL* reference)* NL* ']' ;
reference : qualifiedName | 'head' '(' qualifiedName ')' | 'tail' '(' qualifiedName ')' ;
qualifiedName : identifier ('.' identifier)* ;
predicate : 'require' expression lineEnd ;
expression : orExpression ;
orExpression : andExpression ('or' andExpression)* ;
andExpression : comparisonExpression ('and' comparisonExpression)* ;
comparisonExpression : additiveExpression (comparator additiveExpression)? ;
additiveExpression : multiplicativeExpression (('+' | '-') multiplicativeExpression)* ;
multiplicativeExpression : unaryExpression (('*' | '/' | '%') unaryExpression)* ;
unaryExpression : ('not' | '+' | '-') unaryExpression | primaryExpression ;
primaryExpression
    : qualifiedName '(' (expression (',' expression)*)? ')'
    | qualifiedName | jsonValue | '(' expression ')'
    ;
comparator : '==' | '!=' | '<=' | '>=' | '<' | '>' ;
jsonValue : jsonScalar | jsonObject | jsonArray ;
jsonObject
    : '{' NL* (STRING NL* ':' NL* jsonValue
      (NL* ',' NL* STRING NL* ':' NL* jsonValue)*)? NL* '}'
    ;
jsonArray : '[' NL* (jsonValue (NL* ',' NL* jsonValue)*)? NL* ']' ;
jsonScalar : STRING | signedNumber | 'true' | 'false' | 'null' ;
signedNumber : '-'? NUMBER ;
identifier
    : ID | 'proposition' | 'subject' | 'quantity' | 'unit' | 'scope'
    | 'result' | 'binding' | 'query' | 'method' | 'pattern' | 'apply'
    | 'strict' | 'rank' | 'contrary' | 'reviewed' | 'to' | 'context' | 'via'
    | 'module' | 'import' | 'as' | 'transfer' | 'from' | 'assuming'
    | 'decreases' | 'when' | 'else' | 'head' | 'tail' | 'prefer' | 'over'
    ;
lineEnd : NL+ | EOF ;
ID : [a-zA-Z_] [a-zA-Z_0-9]* ;
NUMBER : ('0' | [1-9] [0-9]*) ('.' [0-9]+)? ([eE] [+-]? [0-9]+)? ;
STRING : '"' (ESC | ~["\\\r\n])* '"' ;
fragment ESC : '\\' (["\\/bfnrt] | 'u' HEX HEX HEX HEX) ;
fragment HEX : [0-9a-fA-F] ;
LINE_COMMENT : '//' ~[\r\n]* -> channel(HIDDEN) ;
BLOCK_COMMENT : '/*' .*? '*/' -> channel(HIDDEN) ;
NL : '\r'? '\n' | '\r' ;
WS : [ \t]+ -> skip ;
