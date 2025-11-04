import logging
import unicodedata
from ..components.cky import process_cky, expand_tree_by_pred, expand_tree_from_cell, enumerate_all_trees_from_cell, normalize_bunsetsu, build_cky_table
from .dep_model_service import batch_predict_dependencies

logger = logging.getLogger(__name__)

def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return text

    text = text.replace("（", "(")
    text = text.replace("）", ")")
    text = text.replace("「", "\"")
    text = text.replace("」", "\"")

    text = unicodedata.normalize('NFKC', text)
    
    return text

def normalize_bunsetsu_data(bunsetsu_data):
    if not isinstance(bunsetsu_data, list):
        return bunsetsu_data
    
    for item in bunsetsu_data:
        if isinstance(item, dict) and "bunsetu" in item:
            for morph in item.get("bunsetu", []):
                if isinstance(morph, dict):
                    if "text" in morph:
                        morph["text"] = normalize_text(morph["text"])
                    if "core" in morph:
                        morph["core"] = normalize_text(morph["core"])
                    if "func" in morph:
                        morph["func"] = normalize_text(morph["func"])
    
    return bunsetsu_data

async def enrich_splits_with_deps(combinations):

    pairs = []
    pair_to_indices = []
    
    for combo_idx, combo in enumerate(combinations):
        for split_idx, split in enumerate(combo.get("splits", [])):
            left_text = split.get("left_text", "")
            right_text = split.get("right_text", "")
            pairs.append({"left": left_text, "right": right_text})
            pair_to_indices.append((combo_idx, split_idx))
    
    logger.info(f"[CKY Service] Enriching {len(pairs)} splits with dependency predictions (batch mode)")

    if pairs:
        predictions = await batch_predict_dependencies(pairs)

        for (combo_idx, split_idx), pred_result in zip(pair_to_indices, predictions):
            combinations[combo_idx]["splits"][split_idx]["pred"] = pred_result["pred"]
            combinations[combo_idx]["splits"][split_idx]["confidence"] = pred_result["confidence"]
    
    return combinations

async def cky_parse_service(bunsetsu_data, request=None):

    bunsetsu_data = normalize_bunsetsu_data(bunsetsu_data)
    
    logger.info(f"[CKY Service] cky_parse_service called")
    logger.info(f"[CKY Service] Input bunsetsu count: {len(bunsetsu_data)}")

    if bunsetsu_data and len(bunsetsu_data) > 0:
        first_item = bunsetsu_data[0]
        if "bunsetu" in first_item and len(first_item["bunsetu"]) > 0:
            first_morph = first_item["bunsetu"][0]
            logger.info(f"[CKY Service] First morph keys: {list(first_morph.keys())}")
            logger.info(f"[CKY Service] First morph data: {first_morph}")
    
    try:

        result = await process_cky(bunsetsu_data)
        
        if result["status"] != "success":
            logger.warning(f"[CKY Service] Error: {result['message']}")
            return result

        combinations = result.get("combinations", [])
        print(f"[DEBUG] combinations count: {len(combinations)}")
        if combinations:
            print(f"[DEBUG] combinations[0] keys: {list(combinations[0].keys())}")
            if "splits" in combinations[0]:
                print(f"[DEBUG] combinations[0]['splits'] count: {len(combinations[0]['splits'])}")
                if combinations[0]['splits']:
                    print(f"[DEBUG] combinations[0]['splits'][0] keys: {list(combinations[0]['splits'][0].keys())}")
        
        enriched_combinations = await enrich_splits_with_deps(combinations)
        result["combinations"] = enriched_combinations
        
        print(f"[DEBUG] enriched_combinations count: {len(enriched_combinations)}")
        if enriched_combinations:
            print(f"[DEBUG] enriched_combinations[0] keys: {list(enriched_combinations[0].keys())}")
            if "splits" in enriched_combinations[0]:
                print(f"[DEBUG] enriched_combinations[0]['splits'] count: {len(enriched_combinations[0]['splits'])}")
                if enriched_combinations[0]['splits']:
                    print(f"[DEBUG] enriched_combinations[0]['splits'][0] keys: {list(enriched_combinations[0]['splits'][0].keys())}")
                    print(f"[DEBUG] enriched_combinations[0]['splits'][0] has pred: {'pred' in enriched_combinations[0]['splits'][0]}")

        span_to_split_info = {}
        for combo in enriched_combinations:
            span = combo.get("span")
            if span:
                span_key = tuple(span)
                span_to_split_info[span_key] = combo.get("splits", [])
        
        print(f"[DEBUG] Created span mapping for {len(span_to_split_info)} spans: {list(span_to_split_info.keys())}")
        logger.info(f"[CKY Service] Created span mapping for {len(span_to_split_info)} spans")

        cky_matrix = result.get("cky_matrix", [])
        print(f"[DEBUG] Matrix shape: {len(cky_matrix)}x{len(cky_matrix[0]) if cky_matrix else 0}")
        enriched_count = 0
        for i, row in enumerate(cky_matrix):
            for j, cell in enumerate(row):
                if cell and "splits" in cell:
                    span_key = (i, j)
                    if span_key in span_to_split_info:
                        combo_splits = span_to_split_info[span_key]

                        for split in cell["splits"]:
                            split_idx = split.get("split_idx")
                            if split_idx is not None and split_idx < len(combo_splits):
                                combo_split = combo_splits[split_idx]
                                split["tree_id"] = combo_split.get("tree_id")
                                split["pred"] = combo_split.get("pred")
                                split["confidence"] = combo_split.get("confidence")
                                enriched_count += 1
                                print(f"[DEBUG] Enriched cell ({i},{j}) split {split_idx}: pred={split.get('pred')}")
        
        print(f"[DEBUG] Enriched total {enriched_count} matrix splits")
        logger.info(f"[CKY Service] Enriched {enriched_count} matrix splits with tree_id/pred/confidence")

        cell_tree_counts = {}
        
        for combo in enriched_combinations:
            span = tuple(combo.get("span", []))
            if span not in cell_tree_counts:
                cell_tree_counts[span] = {"pred1": set(), "pred0": set()}
            
            for split in combo.get("splits", []):
                tree_id = split.get("tree_id")
                pred = split.get("pred")
                
                if tree_id is not None:
                    if pred == 1:
                        cell_tree_counts[span]["pred1"].add(tree_id)
                    elif pred == 0:
                        cell_tree_counts[span]["pred0"].add(tree_id)
        
        print(f"[DEBUG] Counted trees in {len(cell_tree_counts)} cells from combinations")

        for i, row in enumerate(cky_matrix):
            for j, cell in enumerate(row):
                if cell:
                    span_key = (i, j)
                    if span_key in cell_tree_counts:
                        cell["pred1_tree_count"] = len(cell_tree_counts[span_key]["pred1"])
                        cell["pred0_tree_count"] = len(cell_tree_counts[span_key]["pred0"])
                        
                        if (i, j) in [(0, 2), (0, 3), (1, 2)]:
                            print(f"[DEBUG] Cell ({i},{j}): pred1={cell['pred1_tree_count']}, pred0={cell['pred0_tree_count']}, "
                                  f"pred1_ids={sorted(cell_tree_counts[span_key]['pred1'])}, "
                                  f"pred0_ids={sorted(cell_tree_counts[span_key]['pred0'])}")
                    else:
                        cell["pred1_tree_count"] = 0
                        cell["pred0_tree_count"] = 0

        from ..components.cky import normalize_bunsetsu, build_cky_table, enumerate_all_trees_from_cell
        bunsetsu_list = normalize_bunsetsu(bunsetsu_data)
        table = build_cky_table(bunsetsu_list)

        from ..components.cky import enumerate_all_trees_from_cell
        cell_expanded_tree_counts = {}
        
        print(f"[DEBUG] Computing expanded tree counts for all cells...")
        n = len(cky_matrix)
        for i in range(n):
            for j in range(n):
                if i >= j:
                    continue
                
                cell = cky_matrix[i][j]
                if not cell:
                    continue
                
                try:

                    expand_result = enumerate_all_trees_from_cell(table, enriched_combinations, i, j, bunsetsu_list)
                    
                    if expand_result and expand_result.get("tree_list"):
                        tree_list = expand_result.get("tree_list", [])
                        pred1_count = 0
                        pred0_count = 0
                        
                        for tree_item in tree_list:
                            tree_obj = tree_item.get("tree", {})
                            pred = tree_obj.get("pred")
                            if pred == 1:
                                pred1_count += 1
                            elif pred == 0:
                                pred0_count += 1
                        
                        span_key = (i, j)
                        cell_expanded_tree_counts[span_key] = {"pred1": pred1_count, "pred0": pred0_count}
                        print(f"[DEBUG] Cell ({i},{j}): expanded_pred1={pred1_count}, expanded_pred0={pred0_count}")
                    else:
                        span_key = (i, j)
                        cell_expanded_tree_counts[span_key] = {"pred1": 0, "pred0": 0}
                except Exception as e:
                    logger.warning(f"[CKY Service] Cell ({i},{j}) enumeration error: {str(e)}")
                    span_key = (i, j)
                    cell_expanded_tree_counts[span_key] = {"pred1": 0, "pred0": 0}

        print(f"[DEBUG] cell_expanded_tree_counts: {cell_expanded_tree_counts}")
        for i, row in enumerate(cky_matrix):
            for j, cell in enumerate(row):
                if cell:
                    span_key = (i, j)
                    if span_key in cell_expanded_tree_counts:
                        cell["expanded_pred1_count"] = cell_expanded_tree_counts[span_key]["pred1"]
                        cell["expanded_pred0_count"] = cell_expanded_tree_counts[span_key]["pred0"]
                    else:
                        cell["expanded_pred1_count"] = 0
                        cell["expanded_pred0_count"] = 0

        root_trees = {}
        subtree_trees = {}
        expanded_trees = {}

        response = {
            "status": result.get("status", "success"),

            "input_data": {
                "bunsetsu": result.get("bunsetsu", []),
                "description": "各分節の形態素と対応する type フィールド"
            },

            "summary": {
                "total_bunsetsu": result["summary"].get("total_bunsetsu", 0),
                "total_cells": result["summary"].get("total_cells", 0),
                "total_splits": result["summary"].get("total_splits", 0),
                "total_root_trees": len(root_trees),
                "total_subtree_trees": len(subtree_trees),
                "total_all_trees": len(expanded_trees),
                "splits_by_span": result["summary"].get("splits_by_span", {})
            },

            "cky_data": {
                "table": result.get("cky_table", {}),
                "matrix": result.get("cky_matrix", []),
                "combinations": result.get("combinations", []),
                "description": "各 split に pred, confidence, tree_id が付与されている"
            },

            "tree_structures": {
                "trees": result.get("trees", {}),
                "tree_nodes": result.get("tree_nodes", {}),
                "description": "各ノードに types フィールドが含まれている（各分節の形態素の type リスト）"
            },

            "expanded_trees": {
                "root_trees": root_trees,
                "subtree_trees": subtree_trees,
                "all_trees": expanded_trees,
                "description": "pred=1 で展開されたツリー。各ノードに types が含まれている"
            }
        }
        
        logger.info(f"[CKY Service] Success - {response['summary']['total_cells']} cells, "
                   f"{response['summary']['total_splits']} splits enriched, "
                   f"{len(root_trees)} root trees + {len(subtree_trees)} subtrees with pred=1 expanded")
        
        return response
    
    except Exception as e:
        logger.error(f"[CKY Service] Exception: {str(e)}")
        return {
            "status": "error",
            "message": f"サービスエラー: {str(e)}"
        }

async def cky_expand_cell_service(bunsetsu_data, cell_i, cell_j, pred_threshold=1, request=None):
    logger.info(f"[CKY Expand Cell Service] Expanding from cell ({cell_i}, {cell_j})")
    
    try:

        result = await process_cky(bunsetsu_data)
        
        if result["status"] != "success":
            logger.warning(f"[CKY Expand Cell Service] Error: {result['message']}")
            return result

        combinations = result.get("combinations", [])
        enriched_combinations = await enrich_splits_with_deps(combinations)

        bunsetsu_list = normalize_bunsetsu(bunsetsu_data)
        table = build_cky_table(bunsetsu_list)

        expand_result = enumerate_all_trees_from_cell(
            table, enriched_combinations, cell_i, cell_j,
            bunsetsu_list=bunsetsu_list
        )
        
        if expand_result.get("status") != "success":
            logger.warning(f"[CKY Expand Cell Service] Enumeration failed: {expand_result.get('message')}")
            return expand_result
        
        tree_count = len(expand_result.get('tree_list', []))
        logger.info(f"[CKY Expand Cell Service] Success - {tree_count} trees enumerated")
        
        return expand_result
    
    except Exception as e:
        logger.error(f"[CKY Expand Cell Service] Exception: {str(e)}")
        return {
            "status": "error",
            "message": f"サービスエラー: {str(e)}"
        }
