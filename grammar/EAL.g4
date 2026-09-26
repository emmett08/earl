grammar EAL;

program : 'language' STRING ';' declaration* EOF ;
declaration : environmentDecl | toolDecl | evidenceDecl | assumptionDecl
            | reasoningDecl | claimDecl | argumentDecl | objectionDecl
            | patternDecl | applicationDecl ;
environmentDecl : 'environment' identifier '{' predicate+ '}' ;
toolDecl : 'tool' identifier '{' 'version' STRING ';' '}' ;
evidenceDecl : 'evidence' identifier '{' 'tool' identifier ';' 'kind' identifier ';' 'environment' identifier ';'
               'max_age' NUMBER ';' ('input' jsonValue ';')? predicate+ '}' ;
assumptionDecl : 'assumption' identifier '{' 'statement' STRING ';' 'environment' identifier ';'
                 'validate' identifier ';' ('valid_from' STRING ';')?
                 ('valid_until' STRING ';')? '}' ;
reasoningDecl : 'reasoning' identifier '{' 'method' methodName=STRING ';' 'rationale' rationaleText=STRING ';' ('backing' idList ';')? predicate* '}' ;
claimDecl : 'claim' identifier '{' 'statement' STRING ';' 'environment' identifier ';' propositionDecl? '}' ;
propositionDecl : 'proposition' '{' 'subject' STRING ';' 'quantity' STRING ';'
                  'unit' STRING ';' 'scope' STRING ';' 'valid_from' STRING ';'
                  'valid_until' STRING ';' 'query' jsonValue ';' 'result' STRING comparator jsonScalar ';' '}' ;
argumentDecl : 'argument' identifier '{' argumentBody '}' ;
argumentBody : 'conclusion' conclusionRef=identifier ';' 'reasoning' reasoningRef=identifier ';'
               ('evidence' evidenceRefs=idList ';')?
               ('assumptions' assumptionRefs=idList ';')?
               ('premises' premiseRefs=idList ';')? ('binding' bindingRef=identifier ';')? ;
patternDecl : 'pattern' identifier '(' (patternParameter (',' patternParameter)*)? ')'
              '{' argumentBody '}' ;
patternParameter : identifier ':' parameterKind ;
parameterKind : 'claim' | 'reasoning' | 'evidence' | 'assumption' | identifier ;
applicationDecl : 'apply' identifier '=' identifier '(' (patternBinding (',' patternBinding)*)? ')' ';' ;
patternBinding : identifier '=' identifier ;
objectionDecl : 'objection' identifier '{' 'target' targetKind identifier ';'
                ('evidence' evidenceRefs=idList ';')? ('premises' premiseRefs=idList ';')? '}' ;
targetKind : 'claim' | 'reasoning' | 'assumption' | 'argument' | 'objection' ;
idList : identifier (',' identifier)* ;
predicate : 'require' STRING comparator jsonScalar ';' ;
comparator : '==' | '!=' | '<=' | '>=' | '<' | '>' ;
jsonValue : jsonScalar | jsonObject | jsonArray ;
jsonObject : '{' (STRING ':' jsonValue (',' STRING ':' jsonValue)*)? '}' ;
jsonArray : '[' (jsonValue (',' jsonValue)*)? ']' ;
jsonScalar : STRING | NUMBER | 'true' | 'false' | 'null' ;
identifier : ID | 'proposition' | 'subject' | 'quantity' | 'unit' | 'scope' | 'result' | 'binding' | 'query' | 'method' | 'pattern' | 'apply' ;
ID : [a-zA-Z_] [a-zA-Z_0-9]* ;
NUMBER : '-'? ('0' | [1-9] [0-9]*) ('.' [0-9]+)? ([eE] [+-]? [0-9]+)? ;
STRING : '"' (ESC | ~["\\\r\n])* '"' ;
fragment ESC : '\\' (["\\/bfnrt] | 'u' HEX HEX HEX HEX) ;
fragment HEX : [0-9a-fA-F] ;
LINE_COMMENT : '//' ~[\r\n]* -> skip ;
BLOCK_COMMENT : '/*' .*? '*/' -> skip ;
WS : [ \t\r\n]+ -> skip ;
