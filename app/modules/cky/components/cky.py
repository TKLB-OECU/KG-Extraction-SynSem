def normalize_bunsetsu(bunsetsu_data):
    bunsetsu_list = []
    for idx, item in enumerate(bunsetsu_data):
        morphs = item.get("bunsetu", [])
        text = "".join([m.get("text", "") for m in morphs])
        morph_texts = [m.get("text", "") for m in morphs]

        types = [m.get("type", "core") for m in morphs]

        pos_tags = [m.get("pos", "UNK") for m in morphs]

        stem_types = [m.get("stem_type", None) for m in morphs]

        tags = [m.get("tag", "UNK") for m in morphs]
        
        bunsetsu_list.append({
            "id": idx,
            "text": text,
            "morphs": morph_texts,
            "types": types,
            "pos_tags": pos_tags,
            "stem_types": stem_types,
            "tags": tags
        })
    return bunsetsu_list

def build_cky_table(bunsetsu_list):
    n = len(bunsetsu_list)
    table = {}

    for i in range(n):
        table[(i, i)] = {
            "span": [i, i],
            "text": bunsetsu_list[i]["text"],
            "is_terminal": True,
            "splits": []
        }

    for span_length in range(2, n + 1):
        for i in range(n - span_length + 1):
            j = i + span_length - 1

            splits = []
            split_idx = 0
            for k in range(i, j):
                left_span = (i, k)
                right_span = (k + 1, j)

                if left_span in table and right_span in table:
                    left_cell = table[left_span]
                    right_cell = table[right_span]

                    splits.append({
                        "k": k,
                        "split_idx": split_idx,
                        "left": [i, k],
                        "right": [k + 1, j],
                        "left_text": left_cell["text"],
                        "right_text": right_cell["text"]
                    })
                    split_idx += 1

            if splits:
                combined_text = "".join([bunsetsu_list[idx]["text"] for idx in range(i, j + 1)])
                table[(i, j)] = {
                    "span": [i, j],
                    "text": combined_text,
                    "is_terminal": False,
                    "splits": splits
                }
    
    return table

def organize_table_by_span(table, n):
    organized = {}
    
    for span_length in range(1, n + 1):
        span_key = f"span_{span_length}"
        organized[span_key] = []
        
        for i in range(n - span_length + 1):
            j = i + span_length - 1
            if (i, j) in table:
                organized[span_key].append(table[(i, j)])
    
    return organized

def count_splits(table, n):
    total_cells = len(table)
    total_splits = 0
    splits_by_span = {}
    
    for span_length in range(1, n + 1):
        span_key = f"span_{span_length}"
        splits_by_span[span_key] = 0
        
        for i in range(n - span_length + 1):
            j = i + span_length - 1
            if (i, j) in table:
                num_splits = len(table[(i, j)].get("splits", []))
                splits_by_span[span_key] += num_splits
                total_splits += num_splits
    
    return {
        "total_cells": total_cells,
        "total_splits": total_splits,
        "splits_by_span": splits_by_span
    }

def build_cky_matrix(table, n):
    matrix = [[None for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            if (i, j) in table:
                matrix[i][j] = table[(i, j)]
    return matrix

def build_combinations_list(table, n):
    combos = []

    def traverse_and_add_tree_ids(table, i, j, n, path_prefix=""):
        if (i, j) not in table:
            return
        
        cell = table[(i, j)]

        if cell.get("is_terminal", False):
            return
        
        splits_with_ids = []
        for split in cell.get("splits", []):
            split_idx = split.get("split_idx", 0)

            if path_prefix == "":
                tree_id = str(split_idx)
            else:
                tree_id = f"{path_prefix}-{split_idx}"
            
            split_copy = split.copy()
            split_copy["tree_id"] = tree_id
            splits_with_ids.append(split_copy)

            k = split["k"]
            right_i, right_j = split["right"]

            traverse_and_add_tree_ids(table, right_i, right_j, n, tree_id)

        if splits_with_ids:
            combos.append({
                "span": [i, j],
                "text": cell.get("text", ""),
                "splits": splits_with_ids
            })

    if n > 1:
        traverse_and_add_tree_ids(table, 0, n - 1, n, "")

    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) in table:
                cell = table[(i, j)]
                if not cell.get("is_terminal", False):

                    existing = any(c["span"] == [i, j] for c in combos)
                    if not existing:

                        splits_with_ids = []
                        for split_idx, split in enumerate(cell.get("splits", [])):
                            split_copy = split.copy()

                            split_copy["tree_id"] = f"({i},{j})-{split_idx}"
                            splits_with_ids.append(split_copy)
                        
                        if splits_with_ids:
                            combos.append({
                                "span": [i, j],
                                "text": cell.get("text", ""),
                                "splits": splits_with_ids
                            })
    
    return combos

def build_trees(table, n, bunsetsu_list=None):
    trees = {}

    def compute_flat_sequence_for_span(i, j, bunsetsu_list):
        flat_seq = []
        if bunsetsu_list:
            for idx in range(i, j + 1):
                if idx < len(bunsetsu_list):
                    bunsetsu = bunsetsu_list[idx]
                    morphs = bunsetsu.get("morphs", [])
                    types_list = bunsetsu.get("types", [])
                    for morph_text, typ in zip(morphs, types_list):
                        flat_seq.append({"type": typ, "text": morph_text})

        for i_seq in range(1, len(flat_seq) - 1):
            if (flat_seq[i_seq]["type"] == "func" and
                flat_seq[i_seq-1]["type"] == "core" and
                flat_seq[i_seq+1]["type"] == "core"):
                flat_seq[i_seq]["type"] = "core"
        
        return flat_seq

    def build_subtree(i, j, chosen_split_idx=None):

        if (i, j) not in table:
            return None
        cell = table[(i, j)]

        types = []
        if bunsetsu_list and i < len(bunsetsu_list) and j < len(bunsetsu_list):

            for idx in range(i, j + 1):
                if idx < len(bunsetsu_list):
                    bunsetsu = bunsetsu_list[idx]
                    types.extend(bunsetsu.get("types", []))

        flat_seq = compute_flat_sequence_for_span(i, j, bunsetsu_list)
        
        if cell.get("is_terminal", False):
            node = {
                "span": cell.get("span"),
                "text": cell.get("text"),
                "is_terminal": True,
                "flat_sequence": flat_seq
            }
            if types:
                node["types"] = types
            return node

        splits = cell.get("splits", [])
        chosen = None
        if chosen_split_idx is not None:
            for s in splits:
                if s.get("split_idx") == chosen_split_idx:
                    chosen = s
                    break
        if chosen is None and splits:

            chosen = splits[0]

        if chosen is None:

            node = {
                "span": cell.get("span"),
                "text": cell.get("text"),
                "is_terminal": True,
                "flat_sequence": flat_seq
            }
            if types:
                node["types"] = types
            return node

        left_i, left_j = chosen["left"]
        right_i, right_j = chosen["right"]

        left_node = build_subtree(left_i, left_j, None)
        right_node = build_subtree(right_i, right_j, None)

        combined_flat_seq = (left_node.get("flat_sequence", []) + 
                           right_node.get("flat_sequence", []))

        node = {
            "span": cell.get("span"),
            "text": cell.get("text"),
            "is_terminal": False,
            "split": chosen.copy(),
            "flat_sequence": combined_flat_seq
        }
        if types:
            node["types"] = types
        node["children"] = [left_node, right_node]
        
        return node

    for (i, j), cell in list(table.items()):

        if cell.get("is_terminal", False):
            leaf_id = f"leaf-{i}-{j}"

            types = []
            if bunsetsu_list and i < len(bunsetsu_list):
                bunsetsu = bunsetsu_list[i]
                types = bunsetsu.get("types", [])

            flat_seq = compute_flat_sequence_for_span(i, j, bunsetsu_list)
            
            leaf_node = {
                "span": cell.get("span"),
                "text": cell.get("text"),
                "is_terminal": True,
                "flat_sequence": flat_seq,
                "pred": None
            }
            if types:
                leaf_node["types"] = types
            trees[leaf_id] = leaf_node
        else:
            for split in cell.get("splits", []):
                tree_id = split.get("tree_id") or f"{i}-{j}-{split.get('split_idx',0)}"

                left_node = build_subtree(*split.get("left"), None)
                right_node = build_subtree(*split.get("right"), None)

                combined_flat_seq = (left_node.get("flat_sequence", []) + 
                                   right_node.get("flat_sequence", []))

                root_node = {
                    "span": cell.get("span"),
                    "text": cell.get("text"),
                    "is_terminal": False,
                    "split": split.copy(),
                    "flat_sequence": combined_flat_seq,
                    "children": [left_node, right_node],
                    "pred": split.get("pred")
                }

                types = []
                for idx in range(i, j + 1):
                    if bunsetsu_list and idx < len(bunsetsu_list):
                        bunsetsu = bunsetsu_list[idx]
                        types.extend(bunsetsu.get("types", []))
                if types:
                    root_node["types"] = types
                
                trees[tree_id] = root_node

    return trees

def build_tree_structures(table, n, combinations):
    trees = {}
    
    def collect_tree_nodes(table, i, j, n, tree_id, nodes, cells):
        if (i, j) not in table:
            return
        
        cell = table[(i, j)]
        cells.append([i, j])

        if cell.get("is_terminal", False):
            return
        
        for split in cell.get("splits", []):
            sid = split.get("tree_id", "")

            if sid == tree_id or sid.startswith(tree_id + "-"):

                nodes.append({
                    "span": [i, j],
                    "split": split,
                    "text": cell.get("text", "")
                })

                k = split["k"]
                right_i, right_j = split["right"]
                collect_tree_nodes(table, right_i, right_j, n, tree_id, nodes, cells)

    for combo in combinations:
        for split in combo.get("splits", []):
            tree_id = split.get("tree_id", "")
            if tree_id and tree_id not in trees:

                root_i, root_j = combo["span"]

                nodes = []
                cells = []
                collect_tree_nodes(table, root_i, root_j, n, tree_id, nodes, cells)

                if nodes:
                    trees[tree_id] = {
                        "root_span": [root_i, root_j],
                        "root_text": combo.get("text", ""),
                        "cells": cells,
                        "nodes": nodes
                    }
    
    return trees

def get_color_for_pred(pred):
    if pred is None:
        return "gray"
    return "green" if pred == 1 else "red"

def get_split_pred_from_combinations(combinations, span_i, span_j, split_idx=None):
    for combo in combinations:
        if combo.get("span") == [span_i, span_j]:
            splits = combo.get("splits", [])
            if split_idx is not None:

                if split_idx < len(splits):
                    split = splits[split_idx]
                    return {
                        "pred": split.get("pred", 0),
                        "confidence": split.get("confidence", 0.0)
                    }
            else:

                if splits:
                    split = splits[0]
                    return {
                        "pred": split.get("pred", 0),
                        "confidence": split.get("confidence", 0.0)
                    }
    return None

def expand_tree_from_cell(table, combinations, cell_i, cell_j, bunsetsu_list=None, pred_threshold=1):
    
    def get_types_for_span(i, j, bunsetsu_list):
        types = []
        if bunsetsu_list:
            for idx in range(i, j + 1):
                if idx < len(bunsetsu_list):
                    bunsetsu = bunsetsu_list[idx]
                    types.extend(bunsetsu.get("types", []))
        return types
    
    def expand_node(i, j, parent_pred=None):
        if (i, j) not in table:
            return None
        
        cell = table[(i, j)]
        types = get_types_for_span(i, j, bunsetsu_list)

        if cell.get("is_terminal", False):
            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": types,
                "is_terminal": True,
                "pred": None,
                "color": "gray",
                "confidence": None
            }

        if parent_pred is not None and parent_pred < pred_threshold:
            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": types,
                "is_terminal": False,
                "pred": parent_pred,
                "color": get_color_for_pred(parent_pred),
                "confidence": None,
                "is_leaf_due_to_pred": True
            }

        splits = cell.get("splits", [])
        if not splits:
            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": types,
                "is_terminal": False,
                "pred": None,
                "color": "gray",
                "confidence": None
            }

        target_split = splits[0]
        split_info = get_split_pred_from_combinations(
            combinations, i, j, 
            split_idx=target_split.get("split_idx")
        )
        
        if split_info is not None:
            pred = split_info["pred"]
            confidence = split_info["confidence"]
        else:
            pred = target_split.get("pred", 0)
            confidence = target_split.get("confidence", 0.0)
        
        color = get_color_for_pred(pred)

        if pred == 0:

            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": types,
                "is_terminal": False,
                "pred": pred,
                "color": color,
                "confidence": confidence,
                "split": target_split.copy(),
                "is_leaf_due_to_pred": True
            }

        left_i, left_j = target_split.get("left")
        right_i, right_j = target_split.get("right")
        
        left_node = expand_node(left_i, left_j, pred)
        right_node = expand_node(right_i, right_j, pred)
        
        return {
            "span": [i, j],
            "text": cell.get("text", ""),
            "types": types,
            "is_terminal": False,
            "pred": pred,
            "color": color,
            "confidence": confidence,
            "split": target_split.copy(),
            "children": [left_node, right_node]
        }

    if (cell_i, cell_j) not in table:
        return {
            "status": "error",
            "message": f"Cell ({cell_i}, {cell_j}) not found"
        }
    
    cell = table[(cell_i, cell_j)]
    cell_text = cell.get("text", "")
    types = get_types_for_span(cell_i, cell_j, bunsetsu_list)

    if cell.get("is_terminal", False):
        return {
            "status": "success",
            "cell": [cell_i, cell_j],
            "cell_text": cell_text,
            "cell_types": types,
            "is_terminal": True,
            "trees": []
        }

    splits = cell.get("splits", [])
    trees = []
    
    for split_idx, split in enumerate(splits):

        split_info = get_split_pred_from_combinations(
            combinations, cell_i, cell_j, 
            split_idx=split.get("split_idx")
        )
        
        if split_info is not None:
            pred = split_info["pred"]
            confidence = split_info["confidence"]
        else:
            pred = split.get("pred", 0)
            confidence = split.get("confidence", 0.0)
        
        left_i, left_j = split.get("left")
        right_i, right_j = split.get("right")
        left_cell = table.get((left_i, left_j), {})
        right_cell = table.get((right_i, right_j), {})

        left_node = expand_node(left_i, left_j, pred)
        right_node = expand_node(right_i, right_j, pred)
        
        tree_data = {
            "split_idx": split_idx,
            "left": [left_i, left_j],
            "right": [right_i, right_j],
            "left_text": left_cell.get("text", ""),
            "right_text": right_cell.get("text", ""),
            "pred": pred,
            "color": get_color_for_pred(pred),
            "confidence": confidence,
            "tree": {
                "span": [cell_i, cell_j],
                "text": cell_text,
                "types": types,
                "is_terminal": False,
                "pred": pred,
                "color": get_color_for_pred(pred),
                "confidence": confidence,
                "children": [left_node, right_node]
            }
        }
        
        trees.append(tree_data)

    all_patterns = []
    for split_idx, tree_data in enumerate(trees):
        patterns = collect_all_split_patterns(
            table, combinations, tree_data["tree"], bunsetsu_list, pred_threshold, f"split_{split_idx}"
        )
        all_patterns.extend(patterns)
    
    return {
        "status": "success",
        "cell": [cell_i, cell_j],
        "cell_text": cell_text,
        "cell_types": types,
        "is_terminal": False,
        "trees": trees,
        "all_patterns": all_patterns
    }

def enumerate_all_trees_from_cell(table, combinations, cell_i, cell_j, bunsetsu_list=None):
    
    def get_types_for_span(i, j, bunsetsu_list):
        types = []
        if bunsetsu_list:
            for idx in range(i, j + 1):
                if idx < len(bunsetsu_list):
                    bunsetsu = bunsetsu_list[idx]
                    types.extend(bunsetsu.get("types", []))
        return types
    
    def compute_flat_sequence_for_span(i, j, bunsetsu_list):
        flat_seq = []
        if bunsetsu_list:
            for idx in range(i, j + 1):
                if idx < len(bunsetsu_list):
                    bunsetsu = bunsetsu_list[idx]
                    morphs = bunsetsu.get("morphs", [])
                    types_list = bunsetsu.get("types", [])
                    for morph_text, typ in zip(morphs, types_list):
                        flat_seq.append({"type": typ, "text": morph_text})

        for i_seq in range(1, len(flat_seq) - 1):
            if (flat_seq[i_seq]["type"] == "func" and
                flat_seq[i_seq-1]["type"] == "core" and
                flat_seq[i_seq+1]["type"] == "core"):
                flat_seq[i_seq]["type"] = "core"
        
        return flat_seq
    
    def build_all_subtrees(i, j, depth=0):
        if (i, j) not in table:
            return []
        
        cell = table[(i, j)]
        types = get_types_for_span(i, j, bunsetsu_list)
        flat_seq = compute_flat_sequence_for_span(i, j, bunsetsu_list)

        if cell.get("is_terminal", False):
            return [{
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": types,
                "flat_sequence": flat_seq,
                "is_terminal": True,
                "pred": None,
                "color": "gray",
                "confidence": None
            }]

        splits = cell.get("splits", [])
        all_trees = []
        
        for split_idx, split in enumerate(splits):
            left_i, left_j = split.get("left")
            right_i, right_j = split.get("right")

            split_info = get_split_pred_from_combinations(
                combinations, i, j,
                split_idx=split.get("split_idx")
            )
            
            if split_info is not None:
                pred = split_info["pred"]
                confidence = split_info["confidence"]
            else:
                pred = split.get("pred", 0)
                confidence = split.get("confidence", 0.0)

            if pred == 0:
                tree = {
                    "span": [i, j],
                    "text": cell.get("text", ""),
                    "types": types,
                    "flat_sequence": flat_seq,
                    "is_terminal": False,
                    "pred": pred,
                    "color": get_color_for_pred(pred),
                    "confidence": confidence,
                    "is_leaf_due_to_pred": True
                }
                all_trees.append(tree)
                continue

            left_trees = build_all_subtrees(left_i, left_j, depth + 1)
            right_trees = build_all_subtrees(right_i, right_j, depth + 1)

            for left_tree in left_trees:
                for right_tree in right_trees:

                    combined_flat_seq = (left_tree.get("flat_sequence", []) + 
                                        right_tree.get("flat_sequence", []))
                    
                    tree = {
                        "span": [i, j],
                        "text": cell.get("text", ""),
                        "types": types,
                        "flat_sequence": combined_flat_seq,
                        "is_terminal": False,
                        "pred": pred,
                        "color": get_color_for_pred(pred),
                        "confidence": confidence,
                        "children": [left_tree, right_tree]
                    }
                    all_trees.append(tree)
        
        return all_trees if all_trees else [{
            "span": [i, j],
            "text": cell.get("text", ""),
            "types": types,
            "flat_sequence": flat_seq,
            "is_terminal": False,
            "pred": None,
            "color": "gray",
            "confidence": None
        }]

    if (cell_i, cell_j) not in table:
        return {
            "status": "error",
            "message": f"Cell ({cell_i}, {cell_j}) not found"
        }
    
    cell = table[(cell_i, cell_j)]
    cell_text = cell.get("text", "")
    types = get_types_for_span(cell_i, cell_j, bunsetsu_list)
    
    if cell.get("is_terminal", False):
        return {
            "status": "success",
            "cell": [cell_i, cell_j],
            "cell_text": cell_text,
            "cell_types": types,
            "is_terminal": True,
            "tree_list": []
        }

    all_trees = build_all_subtrees(cell_i, cell_j)

    tree_list = []
    for idx, tree in enumerate(all_trees):

        left_text = ""
        right_text = ""
        if tree.get("children") and len(tree["children"]) >= 2:
            left_child = tree["children"][0]
            right_child = tree["children"][1]
            left_span = left_child.get("span", [])
            right_span = right_child.get("span", [])
            
            if left_span and right_span and bunsetsu_list:
                left_text = "".join([bunsetsu_list[i].get("text", "") for i in range(left_span[0], left_span[1] + 1) if i < len(bunsetsu_list)])
                right_text = "".join([bunsetsu_list[i].get("text", "") for i in range(right_span[0], right_span[1] + 1) if i < len(bunsetsu_list)])

        root_pred = tree.get("pred")
        
        tree_list.append({
            "tree_id": f"tree_{idx}",
            "tree": tree,
            "tree_number": idx + 1,
            "left_split": left_text,
            "right_split": right_text,
            "root_pred": root_pred
        })
    
    return {
        "status": "success",
        "cell": [cell_i, cell_j],
        "cell_text": cell_text,
        "cell_types": types,
        "is_terminal": False,
        "tree_list": tree_list
    }

def collect_all_split_patterns(table, combinations, node, bunsetsu_list=None, pred_threshold=1, path=""):
    
    patterns = []
    
    if not node:
        return patterns

    cell_i, cell_j = node.get("span")
    depth = path.count("|")

    if node.get("is_terminal", False):
        return patterns

    if node.get("children") and len(node.get("children", [])) >= 2:
        left_node = node["children"][0]
        right_node = node["children"][1]
        
        patterns.append({
            "path": path,
            "span": [cell_i, cell_j],
            "text": node.get("text", ""),
            "split_idx": 0,
            "left": left_node.get("span"),
            "left_text": left_node.get("text", ""),
            "right": right_node.get("span"),
            "right_text": right_node.get("text", ""),
            "pred": node.get("pred"),
            "color": node.get("color", "gray"),
            "confidence": node.get("confidence", 0.0),
            "depth": depth,
            "is_leaf": False
        })

        left_path = path + "|L" if path else "L"
        right_path = path + "|R" if path else "R"
        
        patterns.extend(collect_all_split_patterns(
            table, combinations, left_node, bunsetsu_list, pred_threshold, left_path
        ))
        patterns.extend(collect_all_split_patterns(
            table, combinations, right_node, bunsetsu_list, pred_threshold, right_path
        ))
    else:

        patterns.append({
            "path": path,
            "span": [cell_i, cell_j],
            "text": node.get("text", ""),
            "split_idx": None,
            "left": None,
            "left_text": None,
            "right": None,
            "right_text": None,
            "pred": node.get("pred"),
            "color": node.get("color", "gray"),
            "confidence": node.get("confidence", 0.0),
            "depth": depth,
            "is_leaf": True
        })
    
    return patterns

def expand_tree_by_pred(table, combinations, tree_id, bunsetsu_list=None, pred_threshold=1):
    
    def find_split_by_tree_id(table, combinations, tree_id):
        for combo in combinations:
            for split in combo.get("splits", []):
                if split.get("tree_id") == tree_id:
                    return split, combo
        return None, None
    
    def get_types_for_span(i, j, bunsetsu_list):
        types = []
        if bunsetsu_list:
            for idx in range(i, j + 1):
                if idx < len(bunsetsu_list):
                    bunsetsu = bunsetsu_list[idx]
                    types.extend(bunsetsu.get("types", []))
        return types
    
    def get_pos_tags_for_span(i, j, bunsetsu_list):
        pos_tags = []
        stem_types = []
        tags = []
        if bunsetsu_list:
            for idx in range(i, j + 1):
                if idx < len(bunsetsu_list):
                    bunsetsu = bunsetsu_list[idx]
                    pos_tags.extend(bunsetsu.get("pos_tags", []))
                    stem_types.extend(bunsetsu.get("stem_types", []))
                    tags.extend(bunsetsu.get("tags", []))
        return pos_tags, stem_types, tags

    root_split, root_combo = find_split_by_tree_id(table, combinations, tree_id)
    if root_split is None:
        return {
            "status": "error",
            "message": f"Tree ID '{tree_id}' not found"
        }
    
    root_span = root_combo["span"]
    root_i, root_j = root_span
    root_text = root_combo.get("text", "")
    root_pred = root_split.get("pred", 0)
    root_color = get_color_for_pred(root_pred)
    root_confidence = root_split.get("confidence", 0.0)

    leaf_spans = []
    expanded_spans = []
    
    def expand_node(i, j, parent_pred=None):
        if (i, j) not in table:
            return None
        
        cell = table[(i, j)]
        types = get_types_for_span(i, j, bunsetsu_list)
        pos_tags, stem_types, tags = get_pos_tags_for_span(i, j, bunsetsu_list)

        if cell.get("is_terminal", False):
            leaf_spans.append([i, j])

            leaf_types = get_types_for_span(i, j, bunsetsu_list)

            terminal_flat_sequence = []

            if cell.get("morphs"):
                for morph_text, typ in zip(cell.get("morphs", []), leaf_types):
                    terminal_flat_sequence.append({
                        "type": typ,
                        "text": morph_text
                    })

            elif bunsetsu_list:
                for k in range(i, j + 1):
                    if k < len(bunsetsu_list):
                        bunsetsu = bunsetsu_list[k]
                        morphs = bunsetsu.get("morphs", [])

                        morphs_types = bunsetsu.get("types", [])
                        for morph_text, typ in zip(morphs, morphs_types):
                            terminal_flat_sequence.append({
                                "type": typ,
                                "text": morph_text
                            })
            
            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": leaf_types,
                "pos_tags": pos_tags,
                "flat_sequence": terminal_flat_sequence,
                "stem_types": stem_types,
                "tags": tags,
                "is_terminal": True,
                "pred": None,
                "color": "gray",
                "confidence": None
            }

        if parent_pred is not None and parent_pred < pred_threshold:

            leaf_spans.append([i, j])

            leaf_types = get_types_for_span(i, j, bunsetsu_list)

            leaf_flat_sequence = []
            if bunsetsu_list:
                for k in range(i, j + 1):
                    if k < len(bunsetsu_list):
                        bunsetsu = bunsetsu_list[k]
                        morphs = bunsetsu.get("morphs", [])

                        morphs_types = bunsetsu.get("types", [])
                        for morph_text, typ in zip(morphs, morphs_types):
                            leaf_flat_sequence.append({
                                "type": typ,
                                "text": morph_text
                            })
            
            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": leaf_types,
                "pos_tags": pos_tags,
                "flat_sequence": leaf_flat_sequence,
                "stem_types": stem_types,
                "tags": tags,
                "is_terminal": False,
                "pred": parent_pred,
                "color": get_color_for_pred(parent_pred),
                "confidence": None,
                "is_leaf_due_to_pred": True
            }

        target_split = None
        if i == root_i and j == root_j:
            target_split = root_split
        else:

            splits = cell.get("splits", [])
            if splits:
                target_split = splits[0]
        
        if target_split is None:

            leaf_spans.append([i, j])

            leaf_types = get_types_for_span(i, j, bunsetsu_list)

            leaf_flat_sequence = []
            if bunsetsu_list:
                for k in range(i, j + 1):
                    if k < len(bunsetsu_list):
                        bunsetsu = bunsetsu_list[k]
                        morphs = bunsetsu.get("morphs", [])

                        morphs_types = bunsetsu.get("types", [])
                        for morph_text, typ in zip(morphs, morphs_types):
                            leaf_flat_sequence.append({
                                "type": typ,
                                "text": morph_text
                            })
            
            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": leaf_types,
                "pos_tags": pos_tags,
                "flat_sequence": leaf_flat_sequence,
                "stem_types": stem_types,
                "tags": tags,
                "is_terminal": False,
                "pred": None,
                "color": "gray",
                "confidence": None
            }

        split_info = get_split_pred_from_combinations(
            combinations, i, j, 
            split_idx=target_split.get("split_idx")
        )
        
        if split_info is not None:
            pred = split_info["pred"]
            confidence = split_info["confidence"]
        else:
            pred = target_split.get("pred", 0)
            confidence = target_split.get("confidence", 0.0)
        
        color = get_color_for_pred(pred)
        
        if pred >= pred_threshold:

            expanded_spans.append([i, j])
            left_i, left_j = target_split.get("left")
            right_i, right_j = target_split.get("right")
            
            left_node = expand_node(left_i, left_j, pred)
            right_node = expand_node(right_i, right_j, pred)

            flat_sequence = _compute_flat_sequence(left_node, right_node)
            
            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": types,
                "pos_tags": pos_tags,
                "flat_sequence": flat_sequence,
                "stem_types": stem_types,
                "tags": tags,
                "is_terminal": False,
                "pred": pred,
                "color": color,
                "confidence": confidence,
                "split": target_split.copy(),
                "children": [left_node, right_node]
            }
        else:

            leaf_spans.append([i, j])

            leaf_flat_sequence = []

            if cell.get("morphs"):
                for morph_text, typ in zip(cell.get("morphs", []), types):
                    leaf_flat_sequence.append({
                        "type": typ,
                        "text": morph_text
                    })

            elif bunsetsu_list:
                for k in range(i, j + 1):
                    if k < len(bunsetsu_list):
                        bunsetsu = bunsetsu_list[k]
                        morphs = bunsetsu.get("morphs", [])
                        morphs_types = bunsetsu.get("types", [])
                        for morph_text, typ in zip(morphs, morphs_types):
                            leaf_flat_sequence.append({
                                "type": typ,
                                "text": morph_text
                            })
            
            return {
                "span": [i, j],
                "text": cell.get("text", ""),
                "types": types,
                "pos_tags": pos_tags,
                "flat_sequence": leaf_flat_sequence,
                "stem_types": stem_types,
                "tags": tags,
                "is_terminal": False,
                "pred": pred,
                "color": color,
                "confidence": confidence,
                "split": target_split.copy(),
                "is_leaf_due_to_pred": True
            }

    def _compute_flat_sequence(left_node, right_node):
        sequence = []
        
        def extract_flat(node):
            if node is None:
                return

            if "flat_sequence" in node and node["flat_sequence"]:
                sequence.extend(node["flat_sequence"])
                return

            types_array = node.get("types", [])
            morphs_array = node.get("morphs")
            span = node.get("span", [])

            if morphs_array and len(morphs_array) == len(types_array):
                for morph_text, typ in zip(morphs_array, types_array):
                    sequence.append({
                        "type": typ,
                        "text": morph_text
                    })

            elif span and len(span) == 2 and bunsetsu_list:
                i, j = span
                for bunsetsu_idx in range(i, j + 1):
                    if bunsetsu_idx < len(bunsetsu_list):
                        bunsetsu = bunsetsu_list[bunsetsu_idx]
                        morphs = bunsetsu.get("morphs", [])
                        morphs_types = bunsetsu.get("types", [])
                        for morph_text, typ in zip(morphs, morphs_types):
                            sequence.append({
                                "type": typ,
                                "text": morph_text
                            })

            elif types_array:
                for typ in types_array:
                    sequence.append({
                        "type": typ,
                        "text": ""
                    })
        
        extract_flat(left_node)
        extract_flat(right_node)
        return sequence

    root_node = expand_node(root_i, root_j, None)
    
    return {
        "status": "success",
        "tree_id": tree_id,
        "root_span": root_span,
        "root_text": root_text,
        "root_pred": root_pred,
        "root_color": root_color,
        "root_confidence": root_confidence,
        "tree": root_node,
        "leaf_spans": leaf_spans,
        "expanded_spans": expanded_spans,
        "stats": {
            "total_leaves": len(leaf_spans),
            "total_expanded": len(expanded_spans)
        }
    }

async def process_cky(bunsetsu_data):
    try:

        bunsetsu_list = normalize_bunsetsu(bunsetsu_data)
        n = len(bunsetsu_list)
        
        if n == 0:
            return {
                "status": "error",
                "message": "分節データが空です"
            }

        table = build_cky_table(bunsetsu_list)

        organized_table = organize_table_by_span(table, n)

        cky_matrix = build_cky_matrix(table, n)
        combinations = build_combinations_list(table, n)

        tree_index = build_tree_structures(table, n, combinations)

        tree_nodes = build_trees(table, n, bunsetsu_list)

        stats = count_splits(table, n)

        return {
            "status": "success",
            "bunsetsu": bunsetsu_list,
            "cky_table": organized_table,
            "cky_matrix": cky_matrix,
            "combinations": combinations,
            "trees": tree_index,
            "tree_nodes": tree_nodes,
            "summary": {
                "total_bunsetsu": n,
                "total_trees": len(tree_index),
                **stats
            }
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"CKY 処理エラー: {str(e)}"
        }
