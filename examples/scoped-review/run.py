"""Collect, assess, compile and export the finite scoped composition example."""
from pathlib import Path
import argparse
import json
import tempfile
from eal.runtime import ReasoningService
from eal.aspic_export import export_aspic_view

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--export-view', type=Path)
    args = parser.parse_args()
    source = (ROOT / 'examples/scoped-review/review.eal').read_text()
    context = {'dataset': 'synthetic'}
    with tempfile.TemporaryDirectory() as temporary:
        service = ReasoningService(ROOT, ROOT / 'examples/scoped-review/tools.toml', Path(temporary)/'records.sqlite3')
        assert service.validate(source)['valid']
        assert service.validate(service.format(source)['source'])['valid']
        collection = service.collect(source, context)
        assessment = service.reason(source, context, collection['collection_id'], now='2026-09-30T10:00:30Z')
        assert assessment['claims']['release.ready']['status'] == 'supported'
        compiled = service.compile_aspic(source, context, collection['collection_id'], goal='release.ready', now='2026-09-30T10:00:30Z', semantics='preferred', query_mode='sceptical')
        assert compiled['formal']['query_status'] == 'accepted'
        view = export_aspic_view(compiled)
        if args.export_view:
            args.export_view.write_text(json.dumps(view,indent=2)+'\n')
        print(json.dumps({'dataset':'synthetic','source_language':'EAL/3','claim_status':compiled['claim_status'],'semantics':view['semantics'],'query_status':view['query_status'],'preference':view['preference'],'arguments':len(view['arguments']),'extensions':len(view['extensions'])}))

if __name__ == '__main__':
    main()
