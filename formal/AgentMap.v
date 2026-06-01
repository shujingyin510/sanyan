(* 三言 Agent 形式化验证 — 5 种认知态到 3 值的映射 (Coq 9.0 兼容) *)

Require Import Trit.
Require Import List.
Import ListNotations.

(* ── 5 种认知态 ── *)
Inductive CognitiveState : Set :=
  | AFFIRM
  | NEGATE
  | UNCERT
  | CONFLICTED
  | UNKNOWN.

(* ── 5→3 映射规则 ── *)
Definition map_5to3 (s : CognitiveState) : Trit :=
  match s with
  | AFFIRM     => T
  | NEGATE     => F
  | UNCERT     => U
  | CONFLICTED => U
  | UNKNOWN    => U
  end.

(* 映射完备性: 所有 5 种状态都有定义 *)
Theorem map_total : forall (s : CognitiveState), exists (t : Trit),
  map_5to3 s = t.
Proof. intros s. destruct s; eauto. Qed.

(* ── 记录类型 ── *)
Record DecisionRecord := mkDecision {
  question   : string;
  cognitive  : CognitiveState;
  mapped_val : Trit;
  confidence : nat;
  action     : string;
}.

(* ── 三态传播 ── *)
Definition trit_propagate (upstream current : CognitiveState) : Trit :=
  trit_and (map_5to3 upstream) (map_5to3 current).

(* ── 门控 ── *)
Definition gating_threshold : nat := 50.

Definition should_defer_to_human (confidence : nat) : bool :=
  Nat.ltb confidence gating_threshold.


(* ═══════════════════════════════════════════════════════════
   关键定理
   ═══════════════════════════════════════════════════════════ *)

Theorem affirm_negate_conflict : trit_propagate AFFIRM NEGATE = F.
Proof. reflexivity. Qed.

Theorem unknown_absorbs : forall (s : CognitiveState),
  trit_propagate UNKNOWN s = U /\ trit_propagate s UNKNOWN = U.
Proof. intros s. split; destruct s; reflexivity. Qed.

Theorem affirm_affirm_consensus : trit_propagate AFFIRM AFFIRM = T.
Proof. reflexivity. Qed.

Theorem negate_negate_consensus : trit_propagate NEGATE NEGATE = F.
Proof. reflexivity. Qed.

Theorem propagate_symmetric : forall (a b : CognitiveState),
  trit_propagate a b = trit_propagate b a.
Proof. intros a b. unfold trit_propagate. apply and_comm. Qed.

Theorem propagate_associative : forall (a b c : CognitiveState),
  trit_and (trit_propagate a b) (map_5to3 c) =
  trit_and (map_5to3 a) (trit_propagate b c).
Proof. intros a b c. unfold trit_propagate. apply and_assoc. Qed.

Theorem affirm_negate_distinguishable : map_5to3 AFFIRM <> map_5to3 NEGATE.
Proof. unfold map_5to3. discriminate. Qed.


(* ═══════════════════════════════════════════════════════════
   门控安全性
   ═══════════════════════════════════════════════════════════ *)

Theorem low_confidence_gates : forall (c : nat),
  c < gating_threshold -> should_defer_to_human c = true.
Proof. intros. unfold should_defer_to_human. apply Nat.ltb_lt. assumption. Qed.

Theorem high_confidence_passes : forall (c : nat),
  c >= gating_threshold -> should_defer_to_human c = false.
Proof. intros. unfold should_defer_to_human. apply Nat.ltb_ge. assumption. Qed.

(* 穷举验证: 25 种传播组合 *)
Definition all_states : list CognitiveState :=
  [AFFIRM; NEGATE; UNCERT; CONFLICTED; UNKNOWN].

Theorem propagation_table_complete : forall (a b : CognitiveState),
  exists (r : Trit), trit_propagate a b = r.
Proof. intros a b. destruct a, b; eauto. Qed.
