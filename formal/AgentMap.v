(* Agent 5→3 认知态映射 — 独立模块，不依赖 Trit *)

Inductive CognitiveState : Set :=
  | AFFIRM | NEGATE | UNCERT | CONFLICTED | UNKNOWN.

Inductive Trit : Set := T | F | U.

Definition map_5to3 (s : CognitiveState) : Trit :=
  match s with
  | AFFIRM => T | NEGATE => F | _ => U
  end.

Definition gating_threshold : nat := 50.
Definition should_defer_to_human (c : nat) : bool := Nat.ltb c gating_threshold.

(* 5→3 映射完备性 *)
Theorem map_total : forall s : CognitiveState, exists t : Trit, map_5to3 s = t.
Proof. intros s. destruct s; eauto. Qed.

(* AFFIRM 和 NEGATE 可区分 *)
Theorem affirm_negate_distinguishable : map_5to3 AFFIRM <> map_5to3 NEGATE.
Proof. unfold map_5to3. discriminate. Qed.

(* U 的来源不可区分（有损压缩） *)
Theorem uncertain_sources_collapse :
  map_5to3 UNCERT = U /\ map_5to3 CONFLICTED = U /\ map_5to3 UNKNOWN = U.
Proof. auto. Qed.

(* 低置信度触发门控 *)
Theorem low_confidence_gates : forall c : nat,
  c < gating_threshold -> should_defer_to_human c = true.
Proof. intros. unfold should_defer_to_human. apply Nat.ltb_lt. assumption. Qed.

(* 高置信度通过门控 *)
Theorem high_confidence_passes : forall c : nat,
  c >= gating_threshold -> should_defer_to_human c = false.
Proof. intros. unfold should_defer_to_human. apply Nat.ltb_ge. assumption. Qed.
