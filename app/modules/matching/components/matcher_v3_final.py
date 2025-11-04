"""
Matcher V3 - 最終版：CKY precomputed flat_sequence を使用

設計原則:
  1. CKY で各ノードの flat_sequence を事前計算（pred=0で止まった構造を反映）
  2. マッチャーは flat_sequence をそのまま使用
  3. パターンを線形トークンに分解
  4. 線形マッチング：slot と literal を順に消費
  5. マッチしたらバインディングを抽出

利点:
  - マッチャーの計算量を削減（flat_sequence は既に計算済み）
  - 正確性：CKY で正しく計算された core/func 列を使用
  - 拡張性：flat_sequence はマッチング以外にも利用可能
"""

import re
import logging
import yaml
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class PatternMatcherV3Final:
    """線形マッチング（precomputed flat_sequence 使用）"""

    SHEN_VERBS = {
        "する", "説明する", "発表する", "検討する", "判断する", "提案する",
        "実施する", "分析する", "評価する", "整理する", "確認する",
        "変更する", "削除する", "追加する", "修正する", "更新する",
        "設定する", "配置する", "配列する", "作成する", "設計する",
        "実行する", "開始する", "終了する", "中止する", "延期する",
        "進行する", "解決する", "対応する", "処理する", "管理する"
    }

    def __init__(self):
        self.logger = logger

        self.parallel_connectives = self._load_parallel_connectives()

    def match_and_extract(
        self,
        tree: Dict,
        pattern_str: str,
        pattern_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        ツリーとパターンをマッチング
        
        Args:
            tree: CKY が生成したツリー（flat_sequence を含む）
            pattern_str: パターン文字列 "[X1]は[X2]を[Y1]" など
            pattern_id: パターンID（ロギング用）
        
        Returns:
            {
              "match": True,
              "pattern": pattern_str,
              "bindings": {X1: "私", X2: "本", Y1: "読む"},
              "triples": [("私", "読む", "本")]
            }
            またはNone
        """
        try:

            flat_seq = tree.get("flat_sequence")
            if not flat_seq:
                self.logger.warning(f"[MatcherV3F] Pattern {pattern_id}: No flat_sequence in tree")
                self.logger.debug(f"[MatcherV3F] Tree keys: {list(tree.keys()) if isinstance(tree, dict) else 'not a dict'}")
                self.logger.debug(f"[MatcherV3F] Tree span: {tree.get('span', 'unknown')}, text: '{tree.get('text', 'unknown')}'")
                return None

            pattern_tokens = self._tokenize_pattern(pattern_str)
            if not pattern_tokens:
                self.logger.warning(f"[MatcherV3F] Pattern {pattern_id}: No tokens in pattern")
                return None

            self.logger.debug(f"[MatcherV3F] Pattern {pattern_id}: tokens={len(pattern_tokens)}, flat_seq len={len(flat_seq)}")
            self.logger.debug(f"[MatcherV3F] Pattern tokens: {pattern_tokens}")
            self.logger.debug(f"[MatcherV3F] Flat sequence: {flat_seq}")

            match_result = self._try_match(pattern_tokens, flat_seq, pattern_str)
            if not match_result:
                self.logger.debug(f"[MatcherV3F] Pattern {pattern_id}: NO MATCH")
                return None

            bindings = match_result["bindings"]
            self.logger.debug(f"[MatcherV3F] Pattern {pattern_id}: Bindings = {bindings}")
            
            triples = self._extract_triples(bindings, pattern_str, tree)
            self.logger.debug(f"[MatcherV3F] Pattern {pattern_id}: Triples = {triples}")

            self.logger.info(f"[MatcherV3F] Pattern {pattern_id}: MATCH - {bindings}")

            return {
                "match": True,
                "pattern": pattern_str,
                "bindings": bindings,
                "triples": triples
            }

        except Exception as e:
            self.logger.error(f"[MatcherV3F] Error: {e}", exc_info=True)
            return None

    def _tokenize_pattern(self, pattern_str: str) -> List[Dict]:
        """
        パターンを [slot] と literal に分割
        
        例: "[X1]は[X2]を[Y1]" →
            [
              {type: "slot", name: "X1"},
              {type: "literal", chars: ["は"]},
              {type: "slot", name: "X2"},
              {type: "literal", chars: ["を"]},
              {type: "slot", name: "Y1"}
            ]
        
        ★特別な処理:
        - "&" は wildcard トークンとして分離
          "[X1]&[X2]" → [{slot:X1}, {wildcard}, {slot:X2}]
        - "*N" プレフィックスは親参照として保存
          "[*1Y1]" → {type: "slot", name: "Y1", parent_depth: 1}
        """
        tokens = []
        parts = re.split(r'(\[[^\]]+\])', pattern_str)

        for part in parts:
            if not part:
                continue

            if re.match(r'\[[^\]]+\]', part):

                slot_content = part[1:-1]

                parent_depth = 0
                if slot_content.startswith('*'):
                    match = re.match(r'\*(\d+)(.+)', slot_content)
                    if match:
                        parent_depth = int(match.group(1))
                        slot_content = match.group(2)
                
                slot_name = slot_content.split('-')[0] if '-' in slot_content else slot_content
                tag = slot_content.split('-')[1] if '-' in slot_content else None

                tokens.append({
                    "type": "slot",
                    "name": slot_name,
                    "tag": tag,
                    "parent_depth": parent_depth
                })
            else:

                if part:

                    for char in part:
                        if char == "&":
                            tokens.append({
                                "type": "wildcard_connective"
                            })
                        else:

                            tokens.append({
                                "type": "literal",
                                "chars": [char]
                            })

        return tokens

    def _try_match(self, pattern_tokens: List[Dict], flat_seq: List[Dict], pattern_str: str = "") -> Optional[Dict]:
        """
        ウィンドウマッチング：各位置から試行
        """
        for start_pos in range(len(flat_seq)):
            result = self._match_from_position(pattern_tokens, flat_seq, start_pos, pattern_str)
            if result:
                return result

        return None

    def _match_from_position(
        self,
        pattern_tokens: List[Dict],
        flat_seq: List[Dict],
        start_pos: int,
        pattern_str: str = ""
    ) -> Optional[Dict]:
        """
        指定位置からマッチング試行
        
        ロジック:
          - slot: core 要素を連続取得（func が来たら終了）
          - literal: func 要素内に含まれる文字を確認
          - ★wildcard_connective: func 要素が任意の並列接続詞にマッチするか確認
          - ★tag が指定されている場合（例：[Y-サ変]）、スロット値をチェック
        """
        bindings = {}
        seq_pos = start_pos
        current_slot_name = None

        slot_info = {}
        if pattern_str:
            slots = re.findall(r'\[([^\]]+)\]', pattern_str)
            for slot_expr in slots:
                parts = slot_expr.split('-')
                slot_name = parts[0].strip()
                tag = parts[1].strip() if len(parts) > 1 else None
                slot_info[slot_name] = {"tag": tag}

        for token in pattern_tokens:
            if token["type"] == "slot":

                slot_name = token["name"]
                parent_depth = token.get("parent_depth", 0)
                core_texts = []

                while seq_pos < len(flat_seq) and flat_seq[seq_pos]["type"] == "core":
                    core_item = flat_seq[seq_pos]
                    core_text = core_item["text"]

                    core_texts.append(core_text)
                    seq_pos += 1

                if not core_texts:

                    self.logger.debug(f"[Match] Fail: slot '{slot_name}' has no core at pos {seq_pos}")
                    return None

                slot_value = "".join(core_texts)

                tag = slot_info.get(slot_name, {}).get("tag")
                if tag == "サ変" and not self._is_shen_compatible(slot_value):
                    self.logger.debug(f"[Match] Fail: slot '{slot_name}' = '{slot_value}' is not サ変 compatible")
                    return None
                
                bindings[slot_name] = slot_value

                slot_start_pos = seq_pos - len(core_texts)
                bindings[f"_{slot_name}_seq_start"] = slot_start_pos
                bindings[f"_{slot_name}_seq_end"] = seq_pos

                if parent_depth > 0:
                    bindings[f"_{slot_name}_parent_depth"] = parent_depth
                
                current_slot_name = slot_name

            elif token["type"] == "wildcard_connective":

                if seq_pos >= len(flat_seq):
                    self.logger.debug(f"[Match] Fail: wildcard_connective at end of sequence")
                    return None

                seq_item = flat_seq[seq_pos]
                seq_type = seq_item["type"]
                func_text = seq_item["text"]

                if seq_type not in ("func", "core"):
                    self.logger.debug(f"[Match] Fail: wildcard_connective - expected func or core, got {seq_type}")
                    return None

                if self._is_any_connective(func_text):
                    seq_pos += 1
                else:
                    self.logger.debug(f"[Match] Fail: wildcard_connective - '{func_text}' is not a connective (type={seq_type})")
                    return None

            elif token["type"] == "literal":

                for char in token["chars"]:
                    if seq_pos >= len(flat_seq):
                        self.logger.debug(f"[Match] Fail: literal '{char}' - sequence ended")
                        return None

                    if flat_seq[seq_pos]["type"] != "func":
                        self.logger.debug(f"[Match] Fail: literal '{char}' - expected func, got {flat_seq[seq_pos]['type']}")
                        return None

                    func_text = flat_seq[seq_pos]["text"]

                    if self._is_connective_match(char, func_text):
                        seq_pos += 1
                    elif char in func_text:

                        seq_pos += 1
                    else:
                        self.logger.debug(f"[Match] Fail: literal '{char}' not in func '{func_text}' (connectives also checked)")
                        return None

        self.logger.debug(f"[Match] Success: bindings={bindings}, consumed seq[{start_pos}:{seq_pos}]")
        return {
            "bindings": bindings,
            "match_start": start_pos,
            "match_end": seq_pos
        }

    def _extract_triples(
        self,
        bindings: Dict,
        pattern_str: str,
        tree: Dict = None
    ) -> List[Tuple[str, str, str]]:
        """
        バインディングからトリプル抽出
        
        ルール（Y を軸に処理）:
          - Y で始まるスロット = 述語（軸）
          - X で始まるスロット = 主語/目的語
          - Y から距離が近い順に X を処理
          - 最短距離 = 目的語
          - 次点距離 = 主語
          - 主語が存在しない場合は φ
        
        ★拡張機能:
          - [Y-サ変]: Y の値が サ変可能か確認
          - [*1Y1]: 親ノード（兄弟ノードが左にある場合）の Y1 を参照
        """
        self.logger.debug(f"[ExtractTriples] ===== START =====")
        self.logger.debug(f"[ExtractTriples] Pattern: {pattern_str}")
        self.logger.debug(f"[ExtractTriples] All bindings: {bindings}")

        import json
        debug_info = {
            "pattern": pattern_str,
            "tree_exists": tree is not None,
            "tree_span": tree.get("span") if tree else None,
            "bindings": bindings
        }
        try:
            with open("debug_extract_triples.json", "w", encoding="utf-8") as f:
                json.dump(debug_info, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.debug(f"[ExtractTriples] Could not write debug file: {e}")
        
        triples = []

        slots = re.findall(r'\[([^\]]+)\]', pattern_str)
        slot_info = {}
        slot_bases = []
        
        for slot_expr in slots:
            parts = slot_expr.split('-')
            base_name = parts[0].strip()
            tag = parts[1].strip() if len(parts) > 1 else None

            parent_depth = 0
            if base_name.startswith('*'):
                match = re.match(r'\*(\d+)(.+)', base_name)
                if match:
                    parent_depth = int(match.group(1))
                    base_name = match.group(2)
            
            slot_info[base_name] = {
                "base": base_name,
                "tag": tag,
                "parent_depth": parent_depth
            }
            slot_bases.append(base_name)

        y_slots = [s for s in slot_bases if s.startswith('Y')]
        x_slots = [s for s in slot_bases if s.startswith('X')]

        parent_bindings = {}
        if tree and any(info.get("parent_depth", 0) > 0 for info in slot_info.values()):
            parent_bindings = self._get_parent_slot_values(tree, slot_info, bindings)

        for y_slot in y_slots:

            if slot_info[y_slot].get("parent_depth", 0) > 0:
                y_text = parent_bindings.get(y_slot)
            else:
                y_text = bindings.get(y_slot)
            
            if not y_text:
                continue

            self.logger.debug(f"[ExtractTriples] Y={y_slot}({y_text})")

            distances = []
            for x_slot in x_slots:

                if slot_info[x_slot].get("parent_depth", 0) > 0:
                    x_text = parent_bindings.get(x_slot)
                else:
                    x_text = bindings.get(x_slot)
                
                if not x_text:
                    continue

                if tree:
                    self.logger.debug(f"[ExtractTriples] Computing distance: Y='{y_text}', X='{x_text}'")
                    distance_from_pred = self._calculate_tree_distance_v3(tree, y_text, x_text, bindings)
                    if distance_from_pred is not None:
                        self.logger.info(f"[ExtractTriples] X={x_slot}({x_text}): tree distance={distance_from_pred}")
                    else:

                        y_pos = slot_bases.index(y_slot) if y_slot in slot_bases else len(slot_bases)
                        x_pos = slot_bases.index(x_slot) if x_slot in slot_bases else len(slot_bases)
                        distance_from_pred = abs(y_pos - x_pos)
                        self.logger.info(f"[ExtractTriples] X={x_slot}({x_text}): tree search FAILED, using slot distance={distance_from_pred}")
                        self.logger.debug(f"[ExtractTriples] Tree distance return None for Y='{y_text}', X='{x_text}'")
                else:

                    y_pos = slot_bases.index(y_slot) if y_slot in slot_bases else len(slot_bases)
                    x_pos = slot_bases.index(x_slot) if x_slot in slot_bases else len(slot_bases)
                    distance_from_pred = abs(y_pos - x_pos)
                    self.logger.info(f"[ExtractTriples] X={x_slot}({x_text}): no tree, using slot distance={distance_from_pred}")

                x_seq_start = bindings.get(f"_{x_slot}_seq_start", 0)
                distances.append((distance_from_pred, x_seq_start, x_slot, x_text))

            distances.sort(reverse=True)
            
            self.logger.info(f"[ExtractTriples] Y={y_slot}({y_text}), all distances after sort: {[(d[0], d[2], d[3]) for d in distances]}")

            if len(distances) >= 2:

                o_text = distances[0][3]

                s_text = distances[1][3]
                
                self.logger.debug(f"[ExtractTriples] Y={y_slot}({y_text}), distances={distances}")
                self.logger.debug(f"[ExtractTriples] O(距離{distances[0][0]})={o_text}, S(距離{distances[1][0]})={s_text}")
                
                triples.append((s_text, y_text, o_text))
            elif len(distances) == 1:

                o_text = distances[0][3]

                self.logger.debug(f"[ExtractTriples] Y={y_slot}({y_text}), O={o_text}, S=φ")
                triples.append(("φ", y_text, o_text))

        return triples

    def _get_parent_slot_values(
        self,
        tree: Dict,
        slot_info: Dict,
        bindings: Dict
    ) -> Dict[str, str]:
        """
        ★親ノード（兄弟ノードが左にある場合）からスロット値を取得
        
        処理:
          1. tree を走査
          2. 各ノードについて、子ノード（left/right）を確認
          3. 左に兄弟（left sibling）がある場合、親ノードから値を参照
        
        戻り値:
          {slot_name: value, ...}
        """
        parent_bindings = {}

        queue = [tree]
        while queue:
            node = queue.pop(0)
            
            if not isinstance(node, dict):
                continue

            if "children" in node:
                for child in node.get("children", []):
                    queue.append(child)

            flat_seq = node.get("flat_sequence", [])
            node_text = node.get("text", "")

            for slot_name, info in slot_info.items():
                if info.get("parent_depth", 0) > 0:

                    if slot_name in bindings:

                        parent_bindings[slot_name] = bindings.get(slot_name)
        
        return parent_bindings

    def _is_shen_compatible(self, verb: str) -> bool:
        """
        ★サ変可能か判定
        
        ルール:
          - SHEN_VERBS に含まれる → True
          - 漢字 + "する" の形式 → True
          - それ以外 → False
        
        例：
          - "説明する" → True (SHEN_VERBS)
          - "実行する" → True (SHEN_VERBS)
          - "動く" → False (サ変不可)
          - "変更する" → True (SHEN_VERBS)
        """

        if verb in self.SHEN_VERBS:
            return True

        if verb.endswith("する"):

            if len(verb) > 2:
                prefix = verb[:-2]

                if any('\u4e00' <= c <= '\u9fff' for c in prefix):
                    return True
        
        return False

    def _get_parent_node_for_y_slots(
        self,
        tree: Dict,
        y_slots: List[str],
        bindings: Dict
    ) -> Optional[Dict]:
        """
        ★*1Y1 処理：複数 Y がある場合の親ノード取得
        
        ロジック:
          1. tree から全ノードを走査
          2. 各ノードで flat_sequence を確認
          3. 複数の Y に対応するテキストが同じノード内に存在するか確認
          4. 見つかった場合、そのノードを親ノード情報として返す
        
        戻り値:
          {
            "span": [i, j],
            "text": "...",
            "flat_sequence": [...],
            "y_texts": [y1_value, y2_value, ...]
          }
          または None
        """
        if not tree or len(y_slots) <= 1:
            return None

        queue = [tree]
        results = []

        while queue:
            node = queue.pop(0)

            if isinstance(node, dict):
                if "children" in node:
                    for child in node.get("children", []):
                        queue.append(child)

                flat_seq = node.get("flat_sequence", [])
                flat_text_set = set(item.get("text", "") for item in flat_seq if item)

                y_texts = []
                y_count = 0
                for y_slot in y_slots:
                    y_text = bindings.get(y_slot)
                    if y_text and y_text in flat_text_set:
                        y_texts.append(y_text)
                        y_count += 1

                if y_count >= 2:
                    results.append({
                        "span": node.get("span"),
                        "text": node.get("text"),
                        "flat_sequence": flat_seq,
                        "y_texts": y_texts,
                        "y_count": y_count
                    })

        if results:
            results.sort(key=lambda x: x["y_count"], reverse=True)
            return results[0]

        return None

    def _load_parallel_connectives(self) -> Dict[str, List[str]]:
        """
        ★並列接続詞辞書を読み込み
        
        app/model/parallel_connectives.yml から読み込んで、
        {
          "と": ["と", "と"],
          "＆": ["&", "＆"],
          "および": ["および", "及び"],
          ...
        }
        のように整理する
        
        戻り値:
          {
            "canonical_form": [list_of_synonyms],
            ...
          }
        """
        connectives_dict = {}
        
        try:

            current_dir = os.path.dirname(os.path.abspath(__file__))
            yml_path = os.path.join(current_dir, "../../../model/parallel_connectives.yml")
            yml_path = os.path.normpath(yml_path)
            
            if not os.path.exists(yml_path):
                self.logger.warning(f"[Connectives] YAML ファイル不見: {yml_path}")
                return {}
            
            with open(yml_path, 'r', encoding='utf-8') as f:
                connectives_list = yaml.safe_load(f) or []

            for conn in connectives_list:
                if isinstance(conn, str):
                    conn = conn.strip()
                    if conn:

                        if conn not in connectives_dict:
                            connectives_dict[conn] = [conn]
                        else:
                            connectives_dict[conn].append(conn)
            
            self.logger.info(f"[Connectives] {len(connectives_dict)} 個の接続詞を読み込み")
            
        except Exception as e:
            self.logger.error(f"[Connectives] 読み込みエラー: {e}")
            return {}
        
        return connectives_dict

    def _is_connective_match(self, pattern_literal: str, seq_text: str) -> bool:
        """
        ★パターンリテラルが flat_sequence のテキストにマッチするか確認
        
        ロジック:
          1. 完全一致チェック
          2. 並列接続詞辞書でシノニム確認
          
        例：
          - pattern_literal="と", seq_text="と" → True
          - pattern_literal="と", seq_text="&" → False (直接は含まれない)
          - pattern_literal="&", seq_text="＆" → 可能性あり（辞書で確認）
        """

        if pattern_literal == seq_text:
            return True

        if pattern_literal in self.parallel_connectives:
            synonyms = self.parallel_connectives[pattern_literal]
            if seq_text in synonyms:
                return True

        if seq_text in self.parallel_connectives:
            synonyms = self.parallel_connectives[seq_text]
            if pattern_literal in synonyms:
                return True
        
        return False

    def _is_any_connective(self, seq_text: str) -> bool:
        """
        ★seq_text が任意の並列接続詞にマッチするかを確認
        
        wildcard_connective トークン（パターンの &）用
        
        ロジック:
          - seq_text が parallel_connectives のキーまたは値に含まれるなら True
          
        例:
          - seq_text="と" → True (キーとして存在)
          - seq_text="＆" → True (値として存在)
          - seq_text="を" → False (接続詞ではない)
        """

        if seq_text in self.parallel_connectives:
            return True

        for synonyms in self.parallel_connectives.values():
            if seq_text in synonyms:
                return True
        
        return False

    def _extract_core_text(self, text):
        """
        ノードのテキストから core 形態素のみを抽出
        
        functional 形態素（助詞、助動詞など）を削除して core のみにする
        
        例：
        - "出演者の" → "出演者"（助詞 "の" を除去）
        - "アミターブ・バッチャンが" → "アミターブ・バッチャン"（助詞 "が" を除去）
        - "受賞・受章した" → "受賞・受章"（助動詞を除去）
        """
        if not text:
            return ""

        functional_markers = [
            "ている", "たい", "られた",
            "の", "が", "を", "に", "は", "へ", "から", "まで", "で",
            "た", "だ", "ます", "です", "ない",
        ]
        
        result = text
        for marker in functional_markers:
            if result.endswith(marker):
                result = result[:-len(marker)]
                if result:
                    return result
        
        return text

    def _build_tree_parent_map(self, tree: Dict) -> Tuple[Dict, Dict]:
        """
        ツリーから parent map と span map を構築
        
        戻り値:
            (parent_map, span_map)
            - parent_map: {node_id -> parent_node_id}
            - span_map: {(i, j) -> [node_ids]}  span から該当ノードへの逆参照
        """
        parent_map = {}
        span_map = {}
        node_registry = {}
        
        counter = [0]
        
        def traverse(node, parent_id=None):
            if not isinstance(node, dict):
                return None
            
            node_id = counter[0]
            counter[0] += 1
            
            node_registry[node_id] = node
            
            if parent_id is not None:
                parent_map[node_id] = parent_id

            span = node.get("span")
            if span:
                span_key = tuple(span)
                if span_key not in span_map:
                    span_map[span_key] = []
                span_map[span_key].append(node_id)

            for child in node.get("children", []):
                traverse(child, node_id)
        
        traverse(tree)
        
        return parent_map, span_map, node_registry
    
    def _calculate_tree_distance_v2(
        self, 
        tree: Dict, 
        y_text: str, 
        x_text: str,
        bindings: Dict = None
    ) -> Optional[int]:
        """
        改善版：ツリー構造上での Y と X の距離を計算
        
        ノード検索優先度:
          1. span による精密探索（seq_start/seq_end から計算）
          2. テキスト完全一致
          3. テキスト部分一致
        
        距離定義：
          - Y は葉ノードを想定
          - Y から共通祖先までのステップ数のみを使用（Y→LCA）
        
        Args:
            tree: ツリーノード
            y_text: Y の値
            x_text: X の値
            bindings: バインディング（seq_start/seq_end 情報含む）
        
        Returns:
            ツリー上での距離（Y→LCA のステップ数），見つからない場合は None
        """
        self.logger.debug(f"[TreeDist] START: y_text='{y_text}', x_text='{x_text}'")
        
        if not tree or not isinstance(tree, dict):
            self.logger.debug(f"[TreeDist] FAILED: tree is None or not dict")
            return None

        parent_map, span_map, node_registry = self._build_tree_parent_map(tree)
        self.logger.debug(f"[TreeDist] node_registry size: {len(node_registry)}")

        if not node_registry:
            return None

        def find_best_node(target_text, binding_key=None):
            """
            ターゲットテキストに最も一致するノードを探す
            
            優先度順（flat_sequence は tree structure に依存するため span 方式は不信頼）：
            1. core テキスト完全一致（最優先）
            2. テキスト完全一致
            3. テキスト部分一致
            
            ★重要：seq_start/seq_end による span マッピングは tree の分割に依存し、
                   異なるツリー構造では無効になるため、テキスト比較を優先
            """
            target_core = self._extract_core_text(target_text)
            self.logger.debug(f"[TreeDist] find_best_node: target_text='{target_text}', core='{target_core}'")

            core_match = None
            exact_match = None
            partial_match = None
            
            for nid, node in node_registry.items():
                node_text = node.get("text", "")
                node_core = self._extract_core_text(node_text)

                if node_core == target_core:
                    core_match = nid
                    self.logger.debug(f"[TreeDist] [CORE-MATCH] nid={nid}: node_text='{node_text}', core='{node_core}'")
                    break

                if node_text == target_text:
                    exact_match = nid
                    self.logger.debug(f"[TreeDist] [EXACT-MATCH] nid={nid}: '{node_text}'")

                if target_text in node_text and partial_match is None:
                    partial_match = nid
                    self.logger.debug(f"[TreeDist] [PARTIAL-MATCH] nid={nid}: '{node_text}' contains '{target_text}'")
            
            if core_match is not None:
                self.logger.debug(f"[TreeDist] → RESULT: core_match nid={core_match}")
                return core_match
            
            if exact_match is not None:
                self.logger.debug(f"[TreeDist] → RESULT: exact_match nid={exact_match}")
                return exact_match
            
            if partial_match is not None:
                self.logger.debug(f"[TreeDist] → RESULT: partial_match nid={partial_match}")
                return partial_match
            
            self.logger.debug(f"[TreeDist] → RESULT: NO MATCH for '{target_text}'")
            return None

        y_nid = find_best_node(y_text, "Y1")
        x_nid = find_best_node(x_text, "X1")
        
        if x_nid is None:

            for i in range(1, 10):
                xn_nid = find_best_node(x_text, f"X{i}")
                if xn_nid is not None:
                    x_nid = xn_nid
                    break
        
        self.logger.debug(f"[TreeDist] Nodes found: y_nid={y_nid}, x_nid={x_nid}")
        self.logger.debug(f"[TreeDist] Node registry size: {len(node_registry)}")
        if y_nid is not None:
            self.logger.debug(f"[TreeDist] Y node text: '{node_registry.get(y_nid, {}).get('text', 'N/A')}'")
        if x_nid is not None:
            self.logger.debug(f"[TreeDist] X node text: '{node_registry.get(x_nid, {}).get('text', 'N/A')}'")
        
        if y_nid is None or x_nid is None:
            self.logger.debug(
                f"[TreeDist] Could not find nodes: y_text='{y_text}' (nid={y_nid}), "
                f"x_text='{x_text}' (nid={x_nid})"
            )
            self.logger.debug(f"[TreeDist] Available node texts: {[node_registry.get(nid, {}).get('text', '') for nid in list(node_registry.keys())[:20]]}")
            return None

        def get_ancestor_list(node_id):
            """ノード ID からルートまでの祖先リスト"""
            ancestors = [node_id]
            current = node_id
            while current in parent_map:
                current = parent_map[current]
                ancestors.append(current)
            return ancestors
        
        y_ancestors = get_ancestor_list(y_nid)
        x_ancestors = get_ancestor_list(x_nid)

        y_set = set(y_ancestors)
        common_ancestor = None
        for anc in x_ancestors:
            if anc in y_set:
                common_ancestor = anc
                break
        
        if common_ancestor is None:
            self.logger.debug("[TreeDist] No common ancestor found")
            return None

        distance_y_to_lca = y_ancestors.index(common_ancestor)
        distance_x_to_lca = x_ancestors.index(common_ancestor)
        distance = distance_y_to_lca + distance_x_to_lca
        
        y_node = node_registry.get(y_nid, {})
        x_node = node_registry.get(x_nid, {})
        common_node = node_registry.get(common_ancestor, {})
        
        self.logger.debug(
            f"[TreeDist] Y='{y_node.get('text')}', X='{x_node.get('text')}', "
            f"LCA='{common_node.get('text')}', "
            f"distance(Y→LCA)={distance_y_to_lca}, distance(X→LCA)={distance_x_to_lca}, "
            f"total={distance}"
        )
        
        return distance

    def _calculate_tree_distance_v3(
        self,
        tree: Dict,
        y_text: str,
        x_text: str,
        bindings: Dict = None
    ) -> Optional[int]:
        """
        V3: Y を根とした距離計算
        
        Y を根として、Y からの子孫パスで X までの距離を計算
        - Y は開始点（距離 0）
        - Y の子孫の深さで X までの距離を測定
        - Y の祖先方向は考慮しない（Y が根だから）
        
        Args:
            tree: ツリーノード
            y_text: Y の値（根）
            x_text: X の値（対象）
            bindings: バインディング情報
        
        Returns:
            Y からの子孫距離
        """
        self.logger.debug(f"[TreeDist-v3] START: y_text='{y_text}', x_text='{x_text}'")
        
        if not tree or not isinstance(tree, dict):
            self.logger.debug(f"[TreeDist-v3] FAILED: tree is None or not dict")
            return None

        parent_map, span_map, node_registry = self._build_tree_parent_map(tree)
        
        if not node_registry:
            return None

        def find_best_node(target_text):
            target_core = self._extract_core_text(target_text)
            
            for nid, node in node_registry.items():
                node_text = node.get("text", "")
                node_core = self._extract_core_text(node_text)
                
                if node_core == target_core:
                    return nid
                if node_text == target_text:
                    return nid
            
            for nid, node in node_registry.items():
                node_text = node.get("text", "")
                if target_text in node_text:
                    return nid
            
            return None
        
        y_nid = find_best_node(y_text)
        x_nid = find_best_node(x_text)
        
        self.logger.debug(f"[TreeDist-v3] Found: y_nid={y_nid}, x_nid={x_nid}")
        
        if y_nid is None or x_nid is None:
            self.logger.debug(f"[TreeDist-v3] Nodes not found")
            return None

        def is_descendant(parent_id, child_id, parent_map):
            """child_id が parent_id の子孫かを確認"""
            current = child_id
            while current in parent_map:
                current = parent_map[current]
                if current == parent_id:
                    return True
            return False

        if is_descendant(y_nid, x_nid, parent_map):

            depth = 0
            current = x_nid
            while current != y_nid and current in parent_map:
                current = parent_map[current]
                depth += 1
            
            self.logger.debug(f"[TreeDist-v3] X is descendant of Y: depth={depth}")
            return depth

        y_ancestors = [y_nid]
        current = y_nid
        while current in parent_map:
            current = parent_map[current]
            y_ancestors.append(current)
        
        x_ancestors = [x_nid]
        current = x_nid
        while current in parent_map:
            current = parent_map[current]
            x_ancestors.append(current)

        y_set = set(y_ancestors)
        common_ancestor = None
        x_depth_to_lca = 0
        
        for i, anc in enumerate(x_ancestors):
            if anc in y_set:
                common_ancestor = anc
                x_depth_to_lca = i
                break
        
        if common_ancestor is None:
            self.logger.debug(f"[TreeDist-v3] No common ancestor")
            return None

        y_depth_to_lca = y_ancestors.index(common_ancestor)

        distance = y_depth_to_lca + x_depth_to_lca
        
        self.logger.debug(
            f"[TreeDist-v3] Y->LCA={y_depth_to_lca}, X->LCA={x_depth_to_lca}, total={distance}"
        )
        
        return distance

    def _calculate_tree_distance(self, tree: Dict, y_text: str, x_text: str) -> Optional[int]:
        """
        後方互換性を保つためのラッパー
        bindings 情報なしで距離計算を実行
        """
        return self._calculate_tree_distance_v2(tree, y_text, x_text, bindings=None)
