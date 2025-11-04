import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

async def matching_service(
    tree: Dict,
    bunsetsu_data=None,
    struct_groups: Dict = None,
    connectives: Dict = None,
    selected_patterns: Optional[List[str]] = None,
    request=None
) -> Dict:

    if not isinstance(tree, dict) or "span" not in tree or "flat_sequence" not in tree:
        return {
            "status": "error",
            "triples": [],
            "matched_patterns": [],
            "pattern_status": {}
        }
    
    if struct_groups is None or connectives is None:
        from app.startup import STRUCT_GROUPS, PARALLEL_CONNECTIVES
        if struct_groups is None:
            struct_groups = STRUCT_GROUPS
        if connectives is None:
            connectives = PARALLEL_CONNECTIVES
    
    if not struct_groups:
        return {
            "status": "error",
            "triples": [],
            "matched_patterns": [],
            "pattern_status": {}
        }
    
    from app.modules.matching.components.matcher_v3_final import PatternMatcherV3Final
    
    matcher = PatternMatcherV3Final()
    
    pattern_status = {}
    matched_patterns = []
    all_triples = []
    triples_by_pattern = {}
    
    if selected_patterns:
        selected_pattern_ids = set(int(pid) for pid in selected_patterns if pid)
    else:
        selected_pattern_ids = None
    
    for pattern_id_str, pattern_item in struct_groups.items():
        pattern_id = int(pattern_id_str)
        
        if selected_pattern_ids is not None and pattern_id not in selected_pattern_ids:
            pattern_status[pattern_id] = "dark_gray"
            continue
        
        if isinstance(pattern_item, str):
            pattern_str = pattern_item
        elif isinstance(pattern_item, dict):
            pattern_str = pattern_item.get("representative_pattern", "")
        else:
            pattern_status[pattern_id] = "dark_gray"
            continue
        
        if not pattern_str:
            pattern_status[pattern_id] = "dark_gray"
            continue
        
        result = matcher.match_and_extract(tree, pattern_str, pattern_id=pattern_id)
        
        if result and result.get("match"):
            pattern_status[pattern_id] = "light"
            matched_patterns.append(pattern_id)
            
            triples = result.get("triples", [])
            triples_by_pattern[pattern_id] = {
                "pattern": pattern_str,
                "triples": triples,
                "bindings": result.get("bindings", {})
            }
            
            for triple in triples:
                detailed_triple = {
                    "subject": triple[0],
                    "predicate": triple[1],
                    "object": triple[2],
                    "pattern": pattern_str,
                    "pattern_id": pattern_id,
                    "bindings": result.get("bindings", {})
                }
                all_triples.append(detailed_triple)
        else:
            pattern_status[pattern_id] = "dark_gray"
    
    return {
        "status": "success",
        "tree_span": tree.get("span", "unknown"),
        "tree_text": tree.get("text", ""),
        "triples": all_triples,
        "triples_by_pattern": triples_by_pattern,
        "matched_patterns": matched_patterns,
        "pattern_status": pattern_status
    }
