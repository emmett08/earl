grammar EAL;

// EAL/3. Contexts and flows lower to the existing typed EAL/3 IR.
program : NL* 'language' STRING lineEnd (declaration NL*)* EOF ;

declaration
    : contextDecl | environmentDecl | toolDecl | evidenceDecl
    | assumptionDecl | reasoningDecl | claimDecl | argumentDecl
    | objectionDecl | patternDecl | applicationDecl | argumentationDirective
    ;

// Contexts supply defaults, never namespaces or new logical premises.
contextDecl
    : 'context' contextAttribute (',' contextAttribute)*
      '{' NL* (declaration NL*)* '}'
    ;
contextAttribute
    : 'environment' identifier | 'tool' identifier | 'max_age' NUMBER
    | 'valid_from' STRING | 'valid_until' STRING
    ;

environmentDecl : 'environment' identifier '{' NL* predicate+ '}' ;
toolDecl : 'tool' identifier '{' NL* versionField '}' ;
versionField : 'version' STRING lineEnd ;

// Required fields and singleton cardinality are checked after inheritance.
evidenceDecl : 'evidence' identifier '{' NL* evidenceField* '}' ;
evidenceField
    : toolField | kindField | environmentField | maxAgeField | inputField
    | predicate
    ;
toolField : 'tool' identifier lineEnd ;
kindField : 'kind' identifier lineEnd ;
environmentField : 'environment' identifier lineEnd ;
maxAgeField : 'max_age' NUMBER lineEnd ;
inputField : 'input' jsonValue lineEnd ;

assumptionDecl : 'assumption' identifier '{' NL* assumptionField* '}' ;
assumptionField
    : statementField | environmentField | validateField
    | validFromField | validUntilField
    ;
statementField : 'statement' STRING lineEnd ;
validateField : 'validate' identifier lineEnd ;
validFromField : 'valid_from' STRING lineEnd ;
validUntilField : 'valid_until' STRING lineEnd ;

reasoningDecl : 'reasoning' identifier '{' NL* reasoningField* '}' ;
reasoningField : methodField | rationaleField | backingField | predicate ;
methodField : 'method' STRING lineEnd ;
rationaleField : 'rationale' STRING lineEnd ;
backingField : 'backing' referenceList lineEnd ;

claimDecl : 'claim' identifier '{' NL* claimField* '}' ;
claimField : statementField | environmentField | propositionDecl ;
propositionDecl : 'proposition' '{' NL* propositionField* '}' NL* ;
propositionField
    : subjectField | quantityField | unitField | scopeField
    | validFromField | validUntilField | queryField | resultField
    ;
subjectField : 'subject' STRING lineEnd ;
quantityField : 'quantity' STRING lineEnd ;
unitField : 'unit' STRING lineEnd ;
scopeField : 'scope' STRING lineEnd ;
queryField : 'query' jsonValue lineEnd ;
resultField : 'result' key comparator jsonScalar lineEnd ;

argumentDecl : 'argument' identifier '=' NL* argumentFlow lineEnd ;
argumentFlow
    : support NL* 'via' NL* reasoningRef=identifier
      NL* '=>' NL* conclusionRef=identifier
      (NL* 'binding' bindingRef=identifier)?
    ;
support
    : '[' NL* (supportGroup (',' NL* supportGroup)*)? NL* ']'
    ;
supportGroup : supportKind identifier (',' NL* identifier)* ;
supportKind : 'evidence' | 'assumptions' | 'premises' ;

patternDecl
    : 'pattern' identifier '(' NL*
      (patternParameter (',' NL* patternParameter)*)? NL* ')'
      NL* '=' NL* argumentFlow lineEnd
    ;
patternParameter : identifier ':' parameterKind ;
parameterKind : 'claim' | 'reasoning' | 'evidence' | 'assumption' | identifier ;
applicationDecl
    : 'apply' identifier '=' identifier '(' NL*
      (patternBinding (',' NL* patternBinding)*)? NL* ')' lineEnd
    ;
patternBinding : identifier '=' identifier ;

objectionDecl
    : 'objection' identifier '=' NL* objectionSupport NL* '-x>' NL*
      targetKind identifier lineEnd
    ;
objectionSupport
    : '[' NL* (objectionGroup (',' NL* objectionGroup)*)? NL* ']'
    ;
objectionGroup : objectionSupportKind identifier (',' NL* identifier)* ;
objectionSupportKind : 'evidence' | 'premises' ;
targetKind : 'claim' | 'reasoning' | 'assumption' | 'argument' | 'objection' ;

argumentationDirective
    : 'strict' identifier 'reviewed' STRING lineEnd
    | 'rank' identifier NUMBER 'reviewed' STRING lineEnd
    | 'contrary' identifier 'to' identifier 'reviewed' STRING lineEnd
    ;

referenceList : '[' NL* identifier (',' NL* identifier)* NL* ']' ;
// A bare key denotes its exact text, including dots; it is not an expression.
predicate : 'require' key comparator jsonScalar lineEnd ;
key : identifier ('.' identifier)* | STRING ;
comparator : '==' | '!=' | '<=' | '>=' | '<' | '>' ;

jsonValue : jsonScalar | jsonObject | jsonArray ;
jsonObject
    : '{' NL* (STRING NL* ':' NL* jsonValue
      (NL* ',' NL* STRING NL* ':' NL* jsonValue)*)? NL* '}'
    ;
jsonArray
    : '[' NL* (jsonValue (NL* ',' NL* jsonValue)*)? NL* ']'
    ;
jsonScalar : STRING | NUMBER | 'true' | 'false' | 'null' ;

// Retain every identifier spelling admitted by the supplied grammar.
identifier
    : ID | 'proposition' | 'subject' | 'quantity' | 'unit' | 'scope'
    | 'result' | 'binding' | 'query' | 'method' | 'pattern' | 'apply'
    | 'strict' | 'rank' | 'contrary' | 'reviewed' | 'to'
    | 'context' | 'via'
    ;
// EOF permits a final directive/flow without a final newline.
lineEnd : NL+ | EOF ;
ID : [a-zA-Z_] [a-zA-Z_0-9]* ;
NUMBER : '-'? ('0' | [1-9] [0-9]*) ('.' [0-9]+)? ([eE] [+-]? [0-9]+)? ;
STRING : '"' (ESC | ~["\\\r\n])* '"' ;
fragment ESC : '\\' (["\\/bfnrt] | 'u' HEX HEX HEX HEX) ;
fragment HEX : [0-9a-fA-F] ;
LINE_COMMENT : '//' ~[\r\n]* -> channel(HIDDEN) ;
BLOCK_COMMENT : '/*' .*? '*/' -> channel(HIDDEN) ;
NL : '\r'? '\n' | '\r' ;
WS : [ \t]+ -> skip ;
