from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, HTMLResponse
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
async def index_page():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    index = os.path.join(base, 'index.html')
    if os.path.exists(index):
        return FileResponse(index, media_type='text/html')
    html = """
    <html><body><h2>Index page not found</h2><p>Please ensure app/static/index.html exists.</p></body></html>
    """
    return HTMLResponse(html)

@router.get("/api/patterns")
async def patterns_api():
    """
    パターン一覧を取得
    
    レスポンス:
    {
      "patterns": {
        "0": {"representative_pattern": "[X1]は[Y]", ...},
        "1": {"representative_pattern": "[X1]を[Y]する", ...},
        ...
      }
    }
    """
    try:
        import startup
        struct_groups = startup.STRUCT_GROUPS
        
        if not struct_groups:
            logger.error("[Patterns API] Pattern database not loaded")
            return {
                "status": "error",
                "message": "Pattern database not loaded",
                "patterns": {}
            }

        patterns = {}
        for pid, pdata in struct_groups.items():
            patterns[str(pid)] = pdata
        
        logger.info(f"[Patterns API] Returning {len(patterns)} patterns")
        
        return {
            "status": "success",
            "patterns": patterns
        }
    
    except Exception as e:
        logger.error(f"[Patterns API] Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e),
            "patterns": {}
        }

@router.post("/api/bunsetu")
async def bunsetu_api(request: Request, text: str = Body(..., embed=True)):
    logger.info(f"Received text for bunsetu: {text}")
    from modules.bunsetu.service.bunsetu_service import segment_bunsetu_service
    return await segment_bunsetu_service(text, request)

@router.post("/api/cky")
async def cky_api(request: Request):
    """
    CKY パーサー実行 API
    
    リクエスト:
    {
      "data": [ 編集済み分節データ ]
    }
    
    レスポンス:
    {
      "status": "success",
      "cky_matrix": [...],
      "combinations": [...],
      "tree_structures": {...}
    }
    """
    try:
        body = await request.json()
        bunsetsu_data = body.get('data', [])
        
        logger.info(f"[CKY API] Received {len(bunsetsu_data)} bunsetsu items")
        
        from modules.cky.service.cky_service import cky_parse_service
        result = await cky_parse_service(bunsetsu_data, request)
        
        return result
    
    except Exception as e:
        logger.error(f"[CKY API] Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e),
            "cky_matrix": [],
            "combinations": [],
            "tree_structures": {}
        }

@router.post("/api/cky/matching")
async def cky_matching_api(request: Request):
    """
    CKY パーサー + パターンマッチング統合API
    
    リクエスト: 
      - Form 1: { data: 編集済み分節データ } (CKY→マッチング)
      - Form 2: { tree: ツリーノード, bunsetsu_list: 分節情報 } (ツリー選択→マッチング)
    
    処理: 
      1. ツリーを抽出
      2. パターンマッチングを実行
    
    レスポンス:
    {
      "status": "success",
      "triples": [
        ["太郎", "読む", "本"]
      ],
      "pattern_status": {...}
    }
    """
    try:
        body = await request.json()
        logger.debug(f"[CKY Matching API] Request body keys: {body.keys()}")

        if 'data' in body:
            bunsetsu_data = body.get('data', [])
            selected_patterns = body.get('selected_patterns', None)
            
            logger.info(f"[CKY Matching API] Form 1: Received {len(bunsetsu_data)} bunsetsu items")

            from modules.cky.service.cky_service import cky_parse_service
            cky_result = await cky_parse_service(bunsetsu_data, request)
            
            if cky_result.get('status') != 'success':
                logger.error(f"[CKY Matching API] CKY parsing failed: {cky_result.get('message', 'Unknown error')}")
                return {
                    "status": "error",
                    "message": f"CKY parsing failed: {cky_result.get('message', 'Unknown error')}",
                    "triples": []
                }

            tree_structures = cky_result.get('tree_structures', {})
            tree_nodes = tree_structures.get('tree_nodes', {})
            
            if not tree_nodes:
                logger.error("[CKY Matching API] No tree nodes found")
                return {
                    "status": "error",
                    "message": "No tree found",
                    "triples": []
                }

            root_nodes = [k for k in tree_nodes.keys() if not k.startswith('leaf-')]
            if not root_nodes:
                logger.error("[CKY Matching API] No root node found")
                return {
                    "status": "error",
                    "message": "No root node found",
                    "triples": []
                }
            
            root_node_key = root_nodes[-1]
            tree = tree_nodes.get(root_node_key)
            logger.info(f"[CKY Matching API] Using root node: {root_node_key}")

        elif 'tree' in body and 'bunsetsu_list' in body:
            tree = body.get('tree')
            bunsetsu_data = body.get('bunsetsu_list', [])
            selected_patterns = body.get('selected_patterns', None)

            tree_span = tree.get('span', 'unknown') if isinstance(tree, dict) else 'unknown'
            tree_text = tree.get('text', 'unknown') if isinstance(tree, dict) else 'unknown'
            
            logger.info(f"[CKY Matching API] Form 2: Received tree directly with {len(bunsetsu_data)} bunsetsu items")
            logger.info(f"[CKY Matching API] Tree span: {tree_span}, text: {tree_text}")
            logger.debug(f"[CKY Matching API] Tree type: {type(tree)}")
            logger.debug(f"[CKY Matching API] Tree keys: {list(tree.keys()) if isinstance(tree, dict) else 'Not a dict'}")
            
            if not tree:
                logger.error("[CKY Matching API] Tree is empty or None")
                return {
                    "status": "error",
                    "message": "Tree is empty or None",
                    "triples": []
                }
            
            if not isinstance(tree, dict):
                logger.error(f"[CKY Matching API] Tree is not a dict: {type(tree)}")
                return {
                    "status": "error",
                    "message": f"Tree must be a dict, got {type(tree).__name__}",
                    "triples": []
                }

        else:
            logger.error(f"[CKY Matching API] Invalid request format. Body keys: {list(body.keys())}")
            return {
                "status": "error",
                "message": "Invalid request format. Expected either 'data' or 'tree'+'bunsetsu_list'",
                "triples": []
            }
        
        logger.debug(f"[CKY Matching API] Tree structure: {str(tree)[:200]}")

        has_children = 'children' in tree if isinstance(tree, dict) else False
        has_split = 'split' in tree if isinstance(tree, dict) else False
        logger.info(f"[CKY Matching API] Tree has children: {has_children}, has split: {has_split}")
        logger.info(f"[CKY Matching API] Tree is_terminal: {tree.get('is_terminal', 'N/A') if isinstance(tree, dict) else 'N/A'}")

        import startup
        struct_groups = startup.STRUCT_GROUPS
        connectives = startup.PARALLEL_CONNECTIVES
        
        if not struct_groups:
            logger.error("[CKY Matching API] Pattern database not loaded")
            return {
                "status": "error",
                "message": "Pattern database not loaded",
                "triples": []
            }
        
        from modules.matching.service.matching_service import matching_service
        matching_result = await matching_service(
            tree,
            bunsetsu_data,
            struct_groups,
            connectives,
            selected_patterns=selected_patterns
        )

        logger.info(f"[CKY Matching API] Matching result status: {matching_result.get('status')}")
        logger.info(f"[CKY Matching API] Triples count: {len(matching_result.get('triples', []))}")

        pattern_status = matching_result.get('pattern_status', {})
        light_count = sum(1 for v in pattern_status.values() if v == 'light')
        logger.info(f"[CKY Matching API] Pattern status: {light_count} light, {len(pattern_status) - light_count} other")

        response_data = {
            "status": matching_result.get('status', 'success'),
            "triples": matching_result.get('triples', []),
            "matched_patterns": matching_result.get('matched_patterns', []),
            "pattern_status": matching_result.get('pattern_status', {}),
            "structural_analysis": matching_result.get('structural_analysis')
        }

        if response_data['status'] == 'error':
            response_data['message'] = matching_result.get('message', 'Unknown error')
            if 'error_type' in matching_result:
                response_data['error_type'] = matching_result['error_type']
            if 'error_traceback' in matching_result:
                response_data['error_traceback'] = matching_result['error_traceback']
        
        return response_data
    
    except Exception as e:
        logger.error(f"[CKY Matching API] Error: {str(e)}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__,
            "error_traceback": error_traceback,
            "triples": []
        }

@router.post("/api/cky/expand-cell")
async def cky_expand_cell_api(request: Request):
    """
    特定のセル (i, j) からツリーを展開する API
    
    リクエスト:
    {
      "data": 編集済み分節データ,
      "cell": [i, j],        // クリックされたセル
      "pred_threshold": 1     // pred >= threshold のみ展開
    }
    
    レスポンス:
    {
      "status": "success",
      "cell": [i, j],
      "cell_text": "...",
      "cell_types": ["core", "func", ...],
      "is_terminal": bool,
      "trees": [
        {
          "split_idx": 0,
          "left": [i, k],
          "right": [k+1, j],
          "left_text": "...",
          "right_text": "...",
          "pred": 0 or 1,
          "color": "green" or "red",
          "confidence": 0.95,
          "tree": { /* ノード構造 */ }
        },
        ...
      ]
    }
    """
    try:
        body = await request.json()
        bunsetsu_data = body.get('data', [])
        cell = body.get('cell', None)
        pred_threshold = body.get('pred_threshold', 1)
        
        if not cell or len(cell) != 2:
            return {"status": "error", "message": "Invalid cell parameter"}
        
        cell_i, cell_j = cell
        
        logger.info(f"[CKY Expand Cell] Expanding from cell ({cell_i}, {cell_j})")
        
        from modules.cky.service.cky_service import cky_expand_cell_service
        result = await cky_expand_cell_service(bunsetsu_data, cell_i, cell_j, pred_threshold, request)
        
        return result
    
    except Exception as e:
        logger.error(f"[CKY Expand Cell API] Error: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/matching/pattern-status")
async def matching_pattern_status_api(request: Request):
    """
    パターンマッチング可能/不可能を判定
    チェックボックス UI 用
    
    リクエスト:
    {
      "tree": { /* CKY解析済みツリーノード */ },
      "bunsetsu_list": [ /* 文節リスト */ ]
    }
    
    レスポンス:
    {
      "status": "success",
      "patterns": [
        {
          "id": "0",
          "pattern": "[X1]は[X2]を[Y]",
          "func": "ACTION",
          "can_match": true,
          "matched": true,
          "triples": [["太郎", "読む", "本"]],
          "checked": true  // UI でチェックされるべきか
        },
        {
          "id": "100",
          "pattern": "[X1]&[X2]は[X3]を[Y]",
          "func": "PARALLEL",
          "can_match": false,  // マッチ不可
          "matched": false,
          "triples": [],
          "checked": false
        }
      ],
      "summary": {
        "total_patterns": 453,
        "matchable_patterns": 12,
        "matched_patterns": 8,
        "selected_patterns": 5
      }
    }
    """
    try:
        body = await request.json()
        tree = body.get('tree', None)
        bunsetsu_list = body.get('bunsetsu_list', [])
        
        if not tree:
            return {
                "status": "error",
                "message": "Tree is empty",
                "patterns": [],
                "summary": {}
            }

        import sys
        import os
        app_path = os.path.join(os.path.dirname(__file__), '..')
        if app_path not in sys.path:
            sys.path.insert(0, app_path)
        
        import startup
        struct_groups = startup.STRUCT_GROUPS
        connectives = startup.PARALLEL_CONNECTIVES
        
        if not struct_groups:
            return {
                "status": "error",
                "message": "Pattern database not loaded",
                "patterns": []
            }

        try:

            from modules.matching.components.matcher_v3_final import PatternMatcherV3Final
            matcher = PatternMatcherV3Final()
        except ImportError as ie:
            logger.error(f"[Pattern Status API] Import error: {str(ie)}")
            raise
        except Exception as ex:
            logger.error(f"[Pattern Status API] Error during matcher creation: {str(ex)}")
            import traceback
            logger.error(traceback.format_exc())
            raise

        matched_patterns_list = []
        matched_pattern_map = {}
        
        for pattern_id_str, pattern_data in struct_groups.items():
            pattern_id = int(pattern_id_str)
            pattern_str = pattern_data.get("representative_pattern", "") if isinstance(pattern_data, dict) else str(pattern_data)
            
            if not pattern_str:
                continue

            result = matcher.match_and_extract(tree, pattern_str, pattern_id=pattern_id)
            if result and result.get("match"):
                matched_patterns_list.append(pattern_id)
                matched_pattern_map[pattern_id_str] = {
                    "pattern_id": pattern_id,
                    "pattern": pattern_str,
                    "triples": result.get("triples", [])
                }

        patterns_list = []
        matchable_count = len(matched_patterns_list)
        matched_count = len(matched_patterns_list)
        
        for pattern_id, pattern_data in sorted(struct_groups.items(), key=lambda x: int(x[0])):
            pattern_id_str = str(pattern_id)
            is_matched = pattern_id_str in matched_pattern_map
            
            if is_matched:
                pattern_info = matched_pattern_map[pattern_id_str]
                triples = pattern_info.get('triples', [])
            else:

                triples = []
            
            patterns_list.append({
                "id": pattern_id_str,
                "pattern": pattern_data.get("representative_pattern", ""),
                "func": pattern_data.get("func", ""),
                "can_match": is_matched,
                "matched": is_matched,
                "triples": triples,
                "checked": is_matched
            })
        
        return {
            "status": "success",
            "patterns": patterns_list,
            "summary": {
                "total_patterns": len(struct_groups),
                "matchable_patterns": matchable_count,
                "matched_patterns": matched_count,
                "selected_patterns": matched_count
            }
        }
    
    except Exception as e:
        logger.error(f"[Pattern Status API] Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e),
            "patterns": [],
            "summary": {}
        }

@router.post("/api/verify/stage1")
async def verify_stage1_api(request: Request):
    """
    Stage 1: 述語定義判定（言い換え対応）
    
    Gemini を使用して、抽出されたトリプルの述語が、オントロジーに定義されているか、
    また言い換え表現として対応しているかを判定
    
    リクエスト:
    {
      "triple": {"subject": "...", "predicate": "...", "object": "..."},
      "relations": [
        {"label": "...", "domain": "...", "object_class": "..."},
        ...
      ]
    }
    
    レスポンス:
    {
      "matched": true|false,
      "matchedRelation": {...} or null,
      "stage": 1,
      "message": "..."
    }
    """
    try:
        body = await request.json()
        triple = body.get('triple', {})
        relations = body.get('relations', [])
        
        predicate = triple.get('predicate', '')

        matched = None
        partial_matches = []

        predicate_lower = predicate.lower().strip()
        for relation in relations:
            rel_label = relation.get('label', '').lower().strip()

            if rel_label == predicate_lower:
                matched = relation
                break

            if predicate_lower and (predicate_lower in rel_label or rel_label in predicate_lower):
                partial_matches.append(relation)

        if not matched and partial_matches:
            matched = partial_matches[0]

        if matched:

            relations_list = "\n".join([
                f"- {r.get('label')} ({r.get('domain')} → {r.get('object_class')})"
                for r in relations
            ])
            
            local_prompt = f"""【述語定義判定タスク】

抽出された述語: "{predicate}"

オントロジーに定義されているリレーション:
{relations_list}

【判定結果】
述語"{predicate}"は、リレーション"{matched.get('label')}"に完全一致/部分一致しました。"""
            
            return {
                "matched": True,
                "defined": True,
                "matchedRelation": matched,
                "stage": 1,
                "message": f"✓ リレーション \"{matched.get('label')}\" にマッチしました",
                "prompt": local_prompt,
                "gemini_response": f"ローカルマッチング: \"{matched.get('label')}\" に一致しました"
            }

        try:
            import os
            gemini_key = os.environ.get('GEMINI_API_KEY')
            
            if gemini_key:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)

                relations_list = "\n".join([
                    f"- {r.get('label')} ({r.get('domain')} → {r.get('object_class')})"
                    for r in relations
                ])
                
                prompt = f"""【述語定義判定タスク】

抽出された述語: \"{predicate}\"

オントロジーに定義されているリレーション:
{relations_list}

背景:
- 上記の述語が、オントロジーのどのリレーションに対応しているかを判定
- 完全一致だけでなく、言い換え表現や類義語も考慮

【タスク】
1. 述語\"{predicate}\"が以下のどのリレーションに対応しているか判定
2. 対応するリレーションが存在するか確認
3. 対応理由を簡潔に説明

【対応ルール】
- 完全一致:
- 言い換え:
- 類義語:

非対応の場合は「matched": false とする。

【出力形式】
JSON のみ（マークダウンなし）:
{{"matched": true or false, "matchedLabel": "マッチしたリレーション名 or null", "reasoning": "判定理由"}}"""
                
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                gemini_response = response.text.strip()
                
                import json
                result_text = gemini_response

                import re
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    matched_label = result.get('matchedLabel')
                    reasoning = result.get('reasoning', '')
                    
                    if result.get('matched') and matched_label:

                        for relation in relations:
                            if relation.get('label') == matched_label:
                                return {
                                    "matched": True,
                                    "defined": True,
                                    "matchedRelation": relation,
                                    "stage": 1,
                                    "message": f"✓ リレーション \"{matched_label}\" に言い換えマッチしました（{reasoning}）",
                                    "prompt": prompt,
                                    "gemini_response": gemini_response,
                                    "reasoning": reasoning,
                                    "debug_info": {
                                        "match_type": "paraphrase",
                                        "predicate_input": predicate,
                                        "matched_label": matched_label
                                    }
                                }

                        for relation in relations:
                            if matched_label.lower() in relation.get('label', '').lower():
                                return {
                                    "matched": True,
                                    "defined": True,
                                    "matchedRelation": relation,
                                    "stage": 1,
                                    "message": f"✓ リレーション \"{relation.get('label')}\" に言い換えマッチしました",
                                    "prompt": prompt,
                                    "gemini_response": gemini_response,
                                    "reasoning": reasoning,
                                    "debug_info": {
                                        "match_type": "paraphrase_partial",
                                        "predicate_input": predicate,
                                        "matched_label": matched_label,
                                        "actual_label": relation.get('label')
                                    }
                                }
                    else:
                        return {
                            "matched": False,
                            "defined": False,
                            "stage": 1,
                            "message": f"✗ 述語 \"{predicate}\" は定義されていません",
                            "prompt": prompt,
                            "gemini_response": gemini_response,
                            "reasoning": reasoning
                        }
                else:
                    return {
                        "matched": False,
                        "defined": False,
                        "stage": 1,
                        "message": f"✗ Gemini 解析エラー",
                        "prompt": prompt,
                        "gemini_response": gemini_response
                    }
            else:

                return {
                    "matched": False,
                    "defined": False,
                    "stage": 1,
                    "message": f"✗ 述語 \"{predicate}\" は定義されていません（Gemini 未有効）"
                }
        
        except Exception as e:
            logger.warning(f"[Verify Stage1] Gemini error: {str(e)}, returning no match")

            relations_list = "\n".join([
                f"- {r.get('label')} ({r.get('domain')} → {r.get('object_class')})"
                for r in relations
            ])
            
            error_prompt = f"""【述語定義判定タスク】

抽出された述語: "{predicate}"

オントロジーに定義されているリレーション:
{relations_list}

背景:
- 上記の述語が、オントロジーのどのリレーションに対応しているかを判定
- 完全一致だけでなく、言い換え表現や類義語も考慮

【判定結果】
述語"{predicate}"は定義されていません。"""
            
            return {
                "matched": False,
                "defined": False,
                "stage": 1,
                "message": f"✗ 述語 \"{predicate}\" は定義されていません",
                "prompt": error_prompt,
                "gemini_response": f"エラーが発生しました: {str(e)}"
            }
    
    except Exception as e:
        logger.error(f"[Verify Stage1 API] Error: {str(e)}")
        return {
            "matched": False,
            "stage": 1,
            "message": f"エラー: {str(e)}"
        }

@router.post("/api/verify/stage2")
async def verify_stage2_api(request: Request):
    """
    Stage 2: オントロジー方向判定
    
    抽出されたトリプル (S, P, O) がオントロジー定義のどの方向（A or B）に
    該当するかを判定
    
    リクエスト:
    {
      "triple": {"subject": "...", "predicate": "...", "object": "..."},
      "relation": {"label": "...", "domain": "...", "object_class": "..."}
    }
    
    判定ロジック:
    オントロジー: P (domain → object_class)
    
    Pattern A（順方向）: subject ∈ domain AND object ∈ object_class
    Pattern B（逆方向）: subject ∈ object_class AND object ∈ domain
    
    レスポンス:
    {
      "valid": true,
      "pattern": "A" or "B",
      "reasoning": "判定理由"
    }
    """
    try:
        body = await request.json()
        triple = body.get('triple', {})
        relation = body.get('relation', {})
        
        subject = triple.get('subject', '')
        obj = triple.get('object', '')
        domain = relation.get('domain', '')
        object_class = relation.get('object_class', '')
        predicate = triple.get('predicate', '')
        
        try:
            import os
            gemini_key = os.environ.get('GEMINI_API_KEY')
            
            if gemini_key:

                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                
                prompt = f"""【パターン判定】

トリプル: ({subject}, {predicate}, {obj})
述語定義: {predicate} (domain={domain}, object_class={object_class})

判定ルール:
- Pattern A: subject ∈ domain かつ object ∈ object_class
- Pattern B: subject ∈ object_class かつ object ∈ domain

"{subject}" がどのクラスに属するか判定してください。
"{obj}" がどのクラスに属するか判定してください。
その結果に基づいて Pattern A または B を判定してください。

【出力】
{{"pattern": "A" or "B", "reasoning": "判定理由"}}"""
                
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                gemini_response = response.text.strip()
                
                import json
                import re

                json_match = re.search(r'\{.*\}', gemini_response, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        pattern = result.get('pattern', 'A').upper()
                        reasoning = result.get('reasoning', '')

                        if pattern not in ['A', 'B']:
                            pattern = 'A'
                        
                        return {
                            "valid": True,
                            "pattern": pattern,
                            "reasoning": reasoning,
                            "prompt": prompt,
                            "gemini_response": gemini_response,
                            "debug_info": {
                                "triple": {"subject": subject, "predicate": predicate, "object": obj},
                                "relation": {"domain": domain, "object_class": object_class},
                                "pattern_determined": pattern
                            }
                        }
                    except json.JSONDecodeError as e:

                        pattern = 'A'
                        reasoning = "JSON パース失敗のためデフォルト判定"
                        
                        return {
                            "valid": True,
                            "pattern": pattern,
                            "reasoning": reasoning,
                            "prompt": prompt,
                            "gemini_response": gemini_response,
                            "error": f"JSON パース失敗: {str(e)}"
                        }
                else:

                    pattern = 'A'
                    reasoning = "JSON抽出失敗のためデフォルト判定"
                    
                    return {
                        "valid": True,
                        "pattern": pattern,
                        "reasoning": reasoning,
                        "prompt": prompt,
                        "gemini_response": gemini_response,
                        "error": "JSON 抽出失敗"
                    }
            else:

                pattern = 'A'
                reasoning = "簡易判定（Pattern A）"
                
                return {
                    "valid": True,
                    "pattern": pattern,
                    "reasoning": reasoning,
                    "debug_info": {"message": "Gemini API キーなし"}
                }
            
        except Exception as e:
            logger.warning(f"[Verify Stage2] LLM error: {str(e)}, using fallback")
            return {
                "valid": True,
                "pattern": "A",
                "reasoning": f"エラーのためデフォルト判定: {str(e)}",
                "error": str(e)
            }
    
    except Exception as e:
        logger.error(f"[Verify Stage2 API] Error: {str(e)}")
        return {
            "valid": False,
            "pattern": None,
            "reasoning": f"エラー: {str(e)}"
        }

@router.post("/api/verify/step3")
async def verify_step3_api(request: Request):
    """
    Step 3: パラフレーズ用サンプル生成
    
    domain と object_class 各クラスのサンプルエンティティを生成します。
    
    リクエスト:
    {
      "relation": {"label": "...", "domain": "...", "object_class": "..."}
    }
    
    レスポンス:
    {
      "sample_domain": "...",           // domain クラスのサンプル
      "sample_object_class": "..."      // object_class クラスのサンプル
    }
    """
    try:
        body = await request.json()
        relation = body.get('relation', {})
        
        domain = relation.get('domain', '')
        object_class = relation.get('object_class', '')
        predicate = relation.get('label', '')
        
        try:
            import os
            gemini_key = os.environ.get('GEMINI_API_KEY')
            
            if gemini_key:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                
                prompt = f"""Generate one representative example entity for each class.

Domain class: "{domain}"
Object class: "{object_class}"

Generate ONE real-world entity name for the domain class.
Generate ONE real-world entity name for the object class.

Output ONLY valid JSON (no markdown, no explanation):
{{
  "sample_domain": "entity name for {domain}",
  "sample_object_class": "entity name for {object_class}"
}}
"""
                
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                
                gemini_response = response.text.strip()
                
                import json
                import re
                json_match = re.search(r'\{.*\}', gemini_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    sample_domain = result.get('sample_domain', '')
                    sample_object_class = result.get('sample_object_class', '')
                    
                    return {
                        "sample_domain": sample_domain,
                        "sample_object_class": sample_object_class,
                        "prompt": prompt,
                        "gemini_response": gemini_response
                    }
                else:
                    return {
                        "sample_domain": "",
                        "sample_object_class": "",
                        "prompt": prompt,
                        "gemini_response": gemini_response,
                        "error": "JSON抽出失敗"
                    }
            else:
                return {
                    "sample_domain": "",
                    "sample_object_class": "",
                    "error": "Gemini API キーなし"
                }
            
        except Exception as e:
            logger.warning(f"[Verify Step3] LLM error: {str(e)}")
            return {
                "sample_domain": "",
                "sample_object_class": "",
                "error": str(e)
            }
    
    except Exception as e:
        logger.error(f"[Verify Step3 API] Error: {str(e)}")
        return {
            "sample_domain": "",
            "sample_object_class": "",
            "error": str(e)
        }

@router.post("/api/verify/step4")
async def verify_step4_api(request: Request):
    """
    Step 4: パラフレーズ判定（True/False）
    
    パターン（A/B）に基づいて、
    トリプルの主語と目的語が
    生成されたサンプルと同じクラスに属するかを判定します。
    
    Pattern A: subject と sample_domain が同じクラス、
               object と sample_object_class が同じクラス
    Pattern B: subject と sample_object_class が同じクラス、
               object と sample_domain が同じクラス
    
    リクエスト:
    {
      "triple": {"subject": "...", "object": "..."},
      "pattern": "A" or "B",
      "relation": {"domain": "...", "object_class": "..."},
      "sample_domain": "...",
      "sample_object_class": "..."
    }
    
    レスポンス:
    {
      "valid": true|false,
      "subject_class": true|false,
      "object_class": true|false
    }
    """
    try:
        body = await request.json()
        triple = body.get('triple', {})
        pattern = body.get('pattern', 'A')
        relation = body.get('relation', {})
        sample_domain = body.get('sample_domain', '')
        sample_object_class = body.get('sample_object_class', '')
        
        subject = triple.get('subject', '')
        obj = triple.get('object', '')
        domain = relation.get('domain', '')
        object_class = relation.get('object_class', '')

        if pattern == 'B':

            subject_compare_with = sample_object_class
            object_compare_with = sample_domain
        else:

            subject_compare_with = sample_domain
            object_compare_with = sample_object_class
        
        try:
            import os
            gemini_key = os.environ.get('GEMINI_API_KEY')
            
            if gemini_key:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                
                prompt = f"""Determine whether the given entities belong to the same class.

Triple: ({subject}, {relation.get('label', '')}, {obj})
Pattern: {pattern}

Determine the following:

(1) Do "{subject}" and "{subject_compare_with}" belong to the same entity class?
    Both should be members of the "{domain if pattern == 'A' else object_class}" class.
    Example: "Spirited Away" and "The God Father" are both movies (YES)
    Example: "Spirited Away" and "Hayao Miyazaki" are NOT both movies (NO)

(2) Do "{obj}" and "{object_compare_with}" belong to the same entity class?
    Both should be members of the "{object_class if pattern == 'A' else domain}" class.
    Example: "Hayao Miyazaki" and "Steven Spielberg" are both persons (YES)
    Example: "Hayao Miyazaki" and "Spirited Away" are NOT both persons (NO)

Decision Rule:
- valid=true only if BOTH (1) AND (2) are true
- valid=false if either (1) OR (2) is false

Output ONLY valid JSON (no markdown, no explanation):
{{
  "subject_class": true or false,
  "object_class": true or false,
  "valid": true or false
}}
"""
                
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                
                gemini_response = response.text.strip()
                
                import json
                import re
                json_match = re.search(r'\{.*\}', gemini_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    subject_class = result.get('subject_class', False)
                    object_class_check = result.get('object_class', False)
                    valid = result.get('valid', False)
                    
                    return {
                        "valid": valid,
                        "subject_class": subject_class,
                        "object_class": object_class_check,
                        "prompt": prompt,
                        "gemini_response": gemini_response
                    }
                else:
                    return {
                        "valid": False,
                        "subject_class": False,
                        "object_class": False,
                        "prompt": prompt,
                        "gemini_response": gemini_response,
                        "error": "JSON抽出失敗"
                    }
            else:
                return {
                    "valid": False,
                    "subject_class": False,
                    "object_class": False,
                    "error": "Gemini API キーなし"
                }
            
        except Exception as e:
            logger.warning(f"[Verify Step4] LLM error: {str(e)}")
            return {
                "valid": False,
                "subject_class": False,
                "object_class": False,
                "error": str(e)
            }
    
    except Exception as e:
        logger.error(f"[Verify Step4 API] Error: {str(e)}")
        return {
            "valid": False,
            "subject_class": False,
            "object_class": False,
            "error": str(e)
        }

@router.post("/api/verify/stage3")
async def verify_stage3_api(request: Request):
    """
    Stage 3: パラフレーズ検証（レガシー - Stage 4と同じ処理）
    
    元のトリプル（正規化後）について、オントロジーの各クラスのサンプルエンティティと
    比較して、以下を判定します：
    (1) 主語が domain クラスに属するか
    (2) 目的語が object_class クラスに属するか
    
    リクエスト:
    {
      "triple": {"subject": "...", "predicate": "...", "object": "..."},
      "pattern": "A" or "B",
      "relation": {"label": "...", "domain": "...", "object_class": "..."}
    }
    
    レスポンス:
    {
      "valid": true|false
    }
    """
    try:
        body = await request.json()
        triple = body.get('triple', {})
        pattern = body.get('pattern', 'A')
        relation = body.get('relation', {})
        
        subject = triple.get('subject', '')
        obj = triple.get('object', '')
        predicate = triple.get('predicate', '')
        domain = relation.get('domain', '')
        object_class = relation.get('object_class', '')

        if pattern == 'B':
            normalized_subject = obj
            normalized_object = subject
            print(f"[Stage 3] パターン B: トリプルを正規化 ({subject}, {predicate}, {obj}) → ({normalized_subject}, {predicate}, {normalized_object})")
        else:
            normalized_subject = subject
            normalized_object = obj
            print(f"[Stage 3] パターン A: トリプルは既に正規形 ({normalized_subject}, {predicate}, {normalized_object})")
        
        try:
            import os
            gemini_key = os.environ.get('GEMINI_API_KEY')
            
            if gemini_key:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                
                prompt = f"""Based on the following sentence and the definition of the ontology relation, determine whether the given conditions are satisfied.

Sentence: "{normalized_subject} {predicate} {normalized_object}"
Ontology relation: {predicate}({domain}, {object_class})

Determine whether the following paraphrases are semantically correct according to world knowledge.

(1) Is "{normalized_subject}" a member of the "{domain}" class?
    Example: if domain="film", then "Spirited Away" is YES, but "Hayao Miyazaki" is NO (he is a person, not a film).
    Example: if domain="film production company", then "Kyoto Animation" is YES, "Studio Ghibli" is YES.

(2) Is "{normalized_object}" a member of the "{object_class}" class?
    Example: if object_class="person", then "Hayao Miyazaki" is YES, but "Spirited Away" is NO (it is a film, not a person).
    Example: if object_class="film", then "Spirited Away" is YES, "The Wind Rises" is YES.

Decision Rule:
- Output "true" only if BOTH (1) AND (2) are satisfied
- Output "false" if either (1) OR (2) is not satisfied

Output ONLY valid JSON (no markdown, no explanation):
{{
  "valid": true or false
}}
"""
                
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                
                gemini_response = response.text.strip()
                
                import json
                import re
                json_match = re.search(r'\{.*\}', gemini_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    valid = result.get('valid', False)
                    
                    return {
                        "valid": valid,
                        "prompt": prompt,
                        "gemini_response": gemini_response
                    }
                else:
                    return {
                        "valid": False,
                        "prompt": prompt,
                        "gemini_response": gemini_response,
                        "error": "JSON抽出失敗"
                    }
            else:
                return {
                    "valid": False,
                    "error": "Gemini API キーなし"
                }
            
        except Exception as e:
            logger.warning(f"[Verify Stage3] LLM error: {str(e)}")
            return {
                "valid": False,
                "error": str(e)
            }
    
    except Exception as e:
        logger.error(f"[Verify Stage3 API] Error: {str(e)}")
        return {
            "valid": False,
            "error": str(e)
        }

@router.post("/api/matching")
async def matching_api(request: Request):
    """
    パターンマッチング実行 API
    
    リクエスト:
    {
      "tree": { /* CKY解析済みツリーノード */ },
      "bunsetsu_list": [ /* 文節リスト */ ],
      "selected_patterns": [パターンID, ...] (オプション)
    }
    
    レスポンス:
    {
      "status": "success",
      "triples": [["主語", "述語", "目的語"], ...],
      "matched_patterns": [パターンID, ...],
      "pattern_status": {パターンID: "light"|"dark_gray", ...},
      "triples_by_pattern": {パターンID: [トリプル, ...], ...}
    }
    """
    try:
        body = await request.json()
        tree = body.get('tree')
        bunsetsu_list = body.get('bunsetsu_list', [])
        selected_patterns = body.get('selected_patterns', None)
        
        logger.info(f"[Matching API] Tree span: {tree.get('span') if isinstance(tree, dict) else 'N/A'}")
        logger.info(f"[Matching API] Bunsetsu count: {len(bunsetsu_list)}")
        
        if not tree or not isinstance(tree, dict):
            return {
                "status": "error",
                "message": "Invalid tree",
                "triples": [],
                "matched_patterns": [],
                "pattern_status": {}
            }
        
        import startup
        struct_groups = startup.STRUCT_GROUPS
        connectives = startup.PARALLEL_CONNECTIVES
        
        if not struct_groups:
            logger.error("[Matching API] Pattern database not loaded")
            return {
                "status": "error",
                "message": "Pattern database not loaded",
                "triples": [],
                "matched_patterns": [],
                "pattern_status": {}
            }
        
        from modules.matching.service.matching_service import matching_service
        result = await matching_service(
            tree,
            bunsetsu_list,
            struct_groups,
            connectives,
            selected_patterns=selected_patterns,
            request=request
        )
        
        return result
    
    except Exception as e:
        logger.error(f"[Matching API] Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e),
            "triples": [],
            "matched_patterns": [],
            "pattern_status": {}
        }
