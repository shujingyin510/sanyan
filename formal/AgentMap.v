Require Import Trit.

Inductive CognitiveState : Set :=
  | AFFIRM | NEGATE | UNCERT | CONFLICTED | UNKNOWN.

Definition map_5to3 (s : CognitiveState) : Trit :=
  match s with
  | AFFIRM => T | NEGATE => F | _ => U
  end.

Definition trit_propagate (upstream current : CognitiveState) : Trit :=
  trit_and (map_5to3 upstream) (map_5to3 current).

Theorem affirm_negate_conflict : trit_propagate AFFIRM NEGATE = F.
Proof. reflexivity. Qed.

Theorem unknown_absorbs : forall s : CognitiveState,
  trit_propagate UNKNOWN s = U /\ trit_propagate s UNKNOWN = U.
Proof. intros s. split; destruct s; reflexivity. Qed.

Theorem affirm_affirm_consensus : trit_propagate AFFIRM AFFIRM = T.
Proof. reflexivity. Qed.

Theorem propagate_symmetric : forall a b : CognitiveState,
  trit_propagate a b = trit_propagate b a.
Proof. intros a b. unfold trit_propagate. apply and_comm. Qed.

Definition gating_threshold : nat := 50.

Definition should_defer_to_human (confidence : nat) : bool :=
  Nat.ltb confidence gating_threshold.

Theorem low_confidence_gates : forall c : nat,
  c < gating_threshold -> should_defer_to_human c = true.
Proof. intros. unfold should_defer_to_human. apply Nat.ltb_lt. assumption. Qed.
