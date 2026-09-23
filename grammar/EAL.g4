grammar EAL;

program : 'language' STRING ';' declaration* EOF ;
declaration : environmentDecl | toolDecl | evidenceDecl | assumptionDecl
            | reasoningDecl | claimDecl | argumentDecl | objectionDecl ;
environmentDecl : 'environment' identifier '{' predicate+ '}' ;
toolDecl : 'tool' identifier '{' 'version' STRING ';' 'mode' executionMode ';' '}' ;
executionMode : 'deterministic' | 'nondeterministic' ;
evidenceDecl : 'evidence' identifier '{' 'tool' identifier ';' 'kind' identifier ';' 'environment' identifier ';'
               'max_age' NUMBER ';' ('input' jsonValue ';')? predicate+ '}' ;
assumptionDecl : 'assumption' identifier '{' 'statement' STRING ';' 'environment' identifier ';'
                 'validate' identifier ';' ('valid_from' STRING ';')?
                 ('valid_until' STRING ';')? '}' ;
reasoningDecl : 'reasoning' identifier '{' 'mode' reasoningMode ';' 'rationale' STRING ';' ('backing' idList ';')? predicate* '}' ;
reasoningMode : 'structured' | 'deductive' | 'inductive' | 'abductive' | 'causal' | 'counterfactual' | 'analogical' | 'temporal' ;
claimDecl : 'claim' identifier '{' 'statement' STRING ';' 'environment' identifier ';' propositionDecl? '}' ;
propositionDecl : 'proposition' '{' 'subject' STRING ';' 'quantity' STRING ';'
                  'unit' STRING ';' 'scope' STRING ';' 'valid_from' STRING ';'
                  'valid_until' STRING ';' 'query' jsonValue ';' 'result' STRING comparator jsonScalar ';' '}' ;
argumentDecl : 'argument' identifier '{' 'conclusion' identifier ';' 'reasoning' identifier ';'
               ('evidence' evidenceRefs=idList ';')?
               ('assumptions' assumptionRefs=idList ';')?
               ('premises' premiseRefs=idList ';')? ('binding' identifier ';')? '}' ;
objectionDecl : 'objection' identifier '{' 'target' targetKind identifier ';'
                'evidence' idList ';' '}' ;
targetKind : 'claim' | 'reasoning' | 'assumption' ;
idList : identifier (',' identifier)* ;
predicate : 'require' STRING comparator jsonScalar ';' ;
comparator : '==' | '!=' | '<=' | '>=' | '<' | '>' ;
jsonValue : jsonScalar | jsonObject | jsonArray ;
jsonObject : '{' (STRING ':' jsonValue (',' STRING ':' jsonValue)*)? '}' ;
jsonArray : '[' (jsonValue (',' jsonValue)*)? ']' ;
jsonScalar : STRING | NUMBER | 'true' | 'false' | 'null' ;
identifier : ID | 'proposition' | 'subject' | 'quantity' | 'unit' | 'scope' | 'result' | 'binding' | 'query' ;
ID : [a-zA-Z_] [a-zA-Z_0-9]* ;
NUMBER : '-'? ('0' | [1-9] [0-9]*) ('.' [0-9]+)? ([eE] [+-]? [0-9]+)? ;
STRING : '"' (ESC | ~["\\\r\n])* '"' ;
fragment ESC : '\\' (["\\/bfnrt] | 'u' HEX HEX HEX HEX) ;
fragment HEX : [0-9a-fA-F] ;
LINE_COMMENT : '//' ~[\r\n]* -> skip ;
BLOCK_COMMENT : '/*' .*? '*/' -> skip ;
WS : [ \t\r\n]+ -> skip ;
