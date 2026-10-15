from app import cloud_ai
from app.assistant_content import PublicExplanation


def test_formats_have_distinct_cache_entries(monkeypatch):
    cloud_ai.reset_runtime()
    calls=[]
    def generate(model,key,payload):
        calls.append(payload)
        return {'text':'Публичное объяснение.\nВторой шаг.'}
    monkeypatch.setattr(cloud_ai,'_generate',generate)
    fragment=PublicExplanation('guide','example','v1','Пример','Публичный материал')
    for format in ('simple','steps'):
        result=cloud_ai.explain_public_fragment(fragment,fallback=fragment.text,api_key='test',model='gemini-test',format=format)
        assert result['source']=='cloud_ai'
    assert len(calls)==2
    assert 'steps' in str(calls[-1])


def test_example_missing_does_not_call_provider(monkeypatch):
    monkeypatch.setattr(cloud_ai,'_generate',lambda *a: (_ for _ in ()).throw(AssertionError('unexpected provider')))
    fragment=PublicExplanation('guide','example','v1','Пример','Публичный материал')
    result=cloud_ai.explain_public_fragment(fragment,fallback=fragment.text,api_key='test',model='gemini-test',format='example')
    assert result['source']=='authored'
