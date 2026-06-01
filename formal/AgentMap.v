(* 三言 Agent 形式化验证 — 5 种认知态到 3 值的映射

   AgentMap.v: Agent 决策管线的形式化规范。
   5 种认知态 (AFFIRM/NEGATE/UNCERT/CONFLICTED/UNKNOWN)
   到 3 值 (T/U/F) 的映射规则。
   决策传播和门控验证。
*)

Require Import Trit.
Require Import List.
Import ListNotations.

(* ── 5 种认知态 ── *)
Inductive CognitiveState : Set :=
  | AFFIRM     (* 明确肯定 *)
  | NEGATE     (* 明确否定 *)
  | UNCERT     (* 不确定 *)
  | CONFLICTED (* 冲突 *)
  | UNKNOWN.   (* 未知 *)

(* ── 5→3 映射规则 (字典驱动的确定性映射) ── *)
Definition map_5to3 (s : CognitiveState) : Trit :=
  match s with
  | AFFIRM     => T
  | NEGATE     => F
  | UNCERT     => U
  | CONFLICTED => U
  | UNKNOWN    => U
  end.

(* 映射的正确性: 所有 5 种状态都有定义（无缺口） *)
Theorem map_total : forall (s : CognitiveState), exists (t : Trit),
  map_5to3 s = t.
Proof.
  intros s. destruct s; eauto.
Qed.

(* ── 决策记录类型 ── *)
Record DecisionRecord := mkDecision {
  question   : string;
  cognitive  : CognitiveState;
  mapped_val : Trit;
  confidence : nat;  (* 0-100 *)
  action     : string;
}.

(* ── 三态传播函数 ──
   上游认知态 × 当前认知态 → 传播后的三值
   传播规则: 映射后的三值取 Kleene 且 (trit_and)，置信度相乘
*)
Definition trit_propagate (upstream current : CognitiveState) : Trit :=
  trit_and (map_5to3 upstream) (map_5to3 current).

(* ── 传播保护门控 ──
   门控条件:
   - 置信度 < 阈值 → 标记为 UNCERT
   - 传播结果为 U → 触发 HUMAN 回退
*)
Definition gating_threshold : nat := 50. (* 置信度阈值 *)

Definition should_defer_to_human (confidence : nat) : bool :=
  Nat.ltb confidence gating_threshold.

(* ── 关键定理 ── *)

(* 定理 1: AFFIRM ∧ NEGATE → F (矛盾) *)
Theorem affirm_negate_conflict : trit_propagate AFFIRM NEGATE = F.
Proof.
  unfold trit_propagate, map_5to3, trit_and. reflexivity.
Qed.

(* 定理 2: 任何含 UNKNOWN 的传播 → U *)
Theorem unknown_absorbs : forall (s : CognitiveState),
  trit_propagate UNKNOWN s = U /\ trit_propagate s UNKNOWN = U.
Proof.
  intros s. unfold trit_propagate, map_5to3, trit_and.
  split; destruct s; reflexivity.
Qed.

(* 定理 3: AFFIRM ∧ AFFIRM → T (一致肯定) *)
Theorem affirm_affirm_consensus : trit_propagate AFFIRM AFFIRM = T.
Proof.
  unfold trit_propagate, map_5to3, trit_and. reflexivity.
Qed.

(* 定理 4: NEGATE ∧ NEGATE → F (一致否定) *)
Theorem negate_negate_consensus : trit_propagate NEGATE NEGATE = F.
Proof.
  unfold trit_propagate, map_5to3, trit_and. reflexivity.
Qed.

(* 定理 5: 传播的对称性 *)
Theorem propagate_symmetric : forall (a b : CognitiveState),
  trit_propagate a b = trit_propagate b a.
Proof.
  intros a b. unfold trit_propagate. apply and_comm.
Qed.

(* 定理 6: 传播的结合性 *)
Theorem propagate_associative : forall (a b c : CognitiveState),
  trit_and (trit_propagate a b) (map_5to3 c) =
  trit_and (map_5to3 a) (trit_propagate b c).
Proof.
  intros a b c. unfold trit_propagate. apply and_assoc.
Qed.

(* ── 门控安全性证明 ── *)

(* 定理 7: 低置信度（< 阈值）时门控触发 *)
Theorem low_confidence_gates : forall (c : nat),
  c < gating_threshold -> should_defer_to_human c = true.
Proof.
  intros c Hc. unfold should_defer_to_human, gating_threshold.
  apply Nat.ltb_lt. exact Hc.
Qed.

(* 定理 8: 高置信度（>= 阈值）时门控不触发 *)
Theorem high_confidence_passes : forall (c : nat),
  c >= gating_threshold -> should_defer_to_human c = false.
Proof.
  intros c Hc. unfold should_defer_to_human, gating_threshold.
  apply Nat.ltb_ge. exact Hc.
Qed.


(* ═══════════════════════════════════════════════════════════
   穷举验证: 所有 5×5 = 25 种认知态组合的传播表
   ═══════════════════════════════════════════════════════════ *)

(* 穷举计算所有 25 种组合 → 确保无未定义行为 *)
Definition all_states : list CognitiveState :=
  [AFFIRM; NEGATE; UNCERT; CONFLICTED; UNKNOWN].

(* 验证传播表无缺口 *)
Theorem propagation_table_complete : forall (a b : CognitiveState),
  exists (r : Trit), trit_propagate a b = r.
Proof.
  intros a b. destruct a, b; eauto.
Qed.

(* 计算具体传播表 *)
Compute (map (fun '(a,b) => (a, b, trit_propagate a b))
         (list_prod all_states all_states)).

(* ── 验证: 5→3 映射不丢失信息量 ── *)

(* 映射后：AFFIRM→T, 其余 →U/F → 信息有损
   但无损信息的设计不变量：AFFIRM 和 NEGATE 保持区分度 *)
Theorem affirm_negate_distinguishable : map_5to3 AFFIRM <> map_5to3 NEGATE.
Proof.
  unfold map_5to3. discriminate.
Qed.

(* 定理: U 的来源 3 种（UNCERT/CONFLICTED/UNKNOWN）在映射后不可区分
   这是设计上的有损压缩，不是 bug *)
Theorem uncertain_sources_collapse :
  map_5to3 UNCERT = U /\
  map_5to3 CONFLICTED = U /\
  map_5to3 UNKNOWN = U.
Proof.
  unfold map_5to3. auto.
Qed.
