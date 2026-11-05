"""Preview policy: official US level plus existing published clustering tier.

An application index, not a probability of harm or a government-issued score.
"""

FORMULA_VERSION = 'us-official-cluster-v1'


def checked_integer(value, minimum, maximum, label):
    if isinstance(value,bool) or not isinstance(value,int) or not minimum <= value <= maximum:
        raise ValueError(f'{label} is outside its supported integer range.')
    return value


def component_score(us_level, clustering_tier):
    us = None if us_level is None else 10.0-2.5*(checked_integer(us_level,1,4,'US level')-1)
    cluster = None if clustering_tier is None else 10.0-2.0*checked_integer(clustering_tier,0,4,'Clustering tier')
    components=[v for v in [us,cluster] if v is not None]
    return {'safe_trip_score':sum(components)/len(components) if components else None,
            'official_us_component':us,'clustering_component':cluster,
            'coverage':'both' if us is not None and cluster is not None else
                       'us_only' if us is not None else 'clustering_only' if cluster is not None else 'neither',
            'severe_official_warning':us_level==4}


def select_us_level(documents, regional_policy):
    if regional_policy not in {'exclude','highest'}:
        raise ValueError('Select an explicit regional advisory policy.')
    for d in documents:
        if d['source']!='us_state' or d['coverage_scope'] not in {'whole_country','parts'}:
            raise ValueError('Unexpected advisory source or geographic scope.')
        checked_integer(d['us_level'],1,4,'US level')
    whole=[d for d in documents if d['coverage_scope']=='whole_country']
    if whole:
        levels={d['us_level'] for d in whole}
        if len(levels)!=1:
            return None,'conflicting_whole_country_advisories'
        return levels.pop(),'whole_country' if len(whole)==1 else 'matching_whole_country_advisories'
    if documents and regional_policy=='highest':
        return max(d['us_level'] for d in documents),'highest_regional_level'
    return None,'regional_only_excluded' if documents else 'no_mapped_us_advisory'


def preview_scores(countries, published, advisories, regional_policy):
    from collections import Counter,defaultdict
    grouped=defaultdict(list)
    for d in advisories:grouped[d['iso3']].append(d)
    rows=[]
    for country in sorted(countries,key=lambda c:c['iso3']):
        iso3=country['iso3'];previous=published.get(iso3,{})
        tier=previous.get('clustering_score')
        level,status=select_us_level(grouped[iso3],regional_policy)
        result=component_score(level,tier)
        old=previous.get('safe_trip_score');new=result['safe_trip_score']
        # PostgreSQL real can differ slightly from the original decimal formula.
        changed=(old is None)!=(new is None) or (old is not None and new is not None and abs(new-old)>0.00001)
        rows.append({**country,**result,'official_us_level':level,'clustering_tier':tier,
            'us_selection_status':status,'previous_score':old,
            'delta':None if old is None or new is None else new-old,'changed':changed,
            'previous_bert_score':previous.get('bert_score'),
            'source_advisories':grouped[iso3]})
    return {'formula_version':FORMULA_VERSION,'regional_policy':regional_policy,
            'nominal_weights':{'official_us':0.5,'clustering':0.5},
            'missing_policy':'use_available_component_without_imputation',
            'clustering_source':'existing_published_scores.clustering_score',
            'database_written':False,'coverage':dict(Counter(r['coverage'] for r in rows)),
            'changed_countries':sum(r['changed'] for r in rows),
            'review_required':[r['iso3'] for r in rows if r['us_selection_status']=='conflicting_whole_country_advisories'],
            'scores':rows}
