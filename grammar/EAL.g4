grammar EAL;

program : 'language' STRING ';' declaration* EOF ;
declaration : environmentDecl | toolDecl | evidenceDecl | assumptionDecl
            | reasoningDecl | claimDecl | argumentDecl | objectionDecl ;
environmentDecl : 'environment' ID '{' predicate+ '}' ;
toolDecl : 'tool' ID '{' 'version' STRING ';' 'mode' executionMode ';' '}' ;
executionMode : 'deterministic' | 'nondeterministic' ;
evidenceDecl : 'evidence' ID '{' 'tool' ID ';' 'kind' ID ';' 'environment' ID ';'
               'max_age' NUMBER ';' ('input' jsonValue ';')? predicate+ '}' ;
assumptionDecl : 'assumption' ID '{' 'statement' STRING ';' 'environment' ID ';'
                 'validate' ID ';' ('valid_from' STRING ';')?
                 ('valid_until' STRING ';')? '}' ;
reasoningDecl : 'reasoning' ID '{' 'mode' reasoningMode ';' 'rationale' STRING ';' ('backing' idList ';')? predicate* '}' ;
reasoningMode : 'structured' | 'deductive' | 'inductive' | 'abductive' | 'causal' | 'counterfactual' | 'analogical' | 'temporal' ;
claimDecl : 'claim' ID '{' 'statement' STRING ';' 'environment' ID ';' '}' ;
argumentDecl : 'argument' ID '{' 'conclusion' ID ';' 'reasoning' ID ';'
               ('evidence' evidenceRefs=idList ';')?
               ('assumptions' assumptionRefs=idList ';')?
               ('premises' premiseRefs=idList ';')? '}' ;
objectionDecl : 'objection' ID '{' 'target' targetKind ID ';'
                'evidence' idList ';' '}' ;
targetKind : 'claim' | 'reasoning' | 'assumption' ;
idList : ID (',' ID)* ;
predicate : 'require' STRING comparator jsonScalar ';' ;
comparator : '==' | '!=' | '<=' | '>=' | '<' | '>' ;
jsonValue : jsonScalar | jsonObject | jsonArray ;
jsonObject : '{' (STRING ':' jsonValue (',' STRING ':' jsonValue)*)? '}' ;
jsonArray : '[' (jsonValue (',' jsonValue)*)? ']' ;
jsonScalar : STRING | NUMBER | 'true' | 'false' | 'null' ;
ID : [a-zA-Z_] [a-zA-Z_0-9]* ;
NUMBER : '-'? ('0' | [1-9] [0-9]*) ('.' [0-9]+)? ([eE] [+-]? [0-9]+)? ;
STRING : '"' (ESC | ~["\\\r\n])* '"' ;
fragment ESC : '\\' (["\\/bfnrt] | 'u' HEX HEX HEX HEX) ;
fragment HEX : [0-9a-fA-F] ;
LINE_COMMENT : '//' ~[\r\n]* -> skip ;
BLOCK_COMMENT : '/*' .*? '*/' -> skip ;
WS : [ \t\r\n]+ -> skip ;
