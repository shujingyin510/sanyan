(* 三言 形式化验证 — 三值逻辑公理化 (Coq 9.0 兼容) *)

Require Import Lia.

(* ── 三值类型 ── *)
Inductive Trit : Set :=
  | T  (* 真 / + *)
  | F  (* 假 / - *)
  | U. (* 未知 / 0 *)

(* ── 基本运算 ── *)
Definition trit_not (a : Trit) : Trit :=
  match a with
  | T => F
  | F => T
  | U => U
  end.

Definition trit_and (a b : Trit) : Trit :=
  match a, b with
  | T, T => T
  | F, _ => F
  | _, F => F
  | U, _ => U
  | _, U => U
  end.

Definition trit_or (a b : Trit) : Trit :=
  match a, b with
  | F, F => F
  | T, _ => T
  | _, T => T
  | U, _ => U
  | _, U => U
  end.

Definition trit_imp (a b : Trit) : Trit :=
  match a, b with
  | T, F => F
  | T, T => T
  | T, U => U
  | F, _ => T
  | U, T => T
  | U, F => U
  | U, U => U
  end.


(* ═══════════════════════════════════════════════════════════
   代数定律证明
   ═══════════════════════════════════════════════════════════ *)

Theorem not_involutive : forall (a : Trit),
  trit_not (trit_not a) = a.
Proof. intros a. destruct a; reflexivity. Qed.

Theorem and_comm : forall (a b : Trit),
  trit_and a b = trit_and b a.
Proof. intros a b. destruct a, b; reflexivity. Qed.

Theorem or_comm : forall (a b : Trit),
  trit_or a b = trit_or b a.
Proof. intros a b. destruct a, b; reflexivity. Qed.

Theorem and_assoc : forall (a b c : Trit),
  trit_and a (trit_and b c) = trit_and (trit_and a b) c.
Proof. intros a b c. destruct a, b, c; reflexivity. Qed.

Theorem or_assoc : forall (a b c : Trit),
  trit_or a (trit_or b c) = trit_or (trit_or a b) c.
Proof. intros a b c. destruct a, b, c; reflexivity. Qed.

Theorem and_idempotent : forall (a : Trit),
  trit_and a a = a.
Proof. intros a. destruct a; reflexivity. Qed.

Theorem or_idempotent : forall (a : Trit),
  trit_or a a = a.
Proof. intros a. destruct a; reflexivity. Qed.

Theorem de_morgan_and : forall (a b : Trit),
  trit_not (trit_and a b) = trit_or (trit_not a) (trit_not b).
Proof. intros a b. destruct a, b; reflexivity. Qed.

Theorem de_morgan_or : forall (a b : Trit),
  trit_not (trit_or a b) = trit_and (trit_not a) (trit_not b).
Proof. intros a b. destruct a, b; reflexivity. Qed.

Theorem absorb_and : forall (a b : Trit),
  trit_and a (trit_or a b) = a.
Proof. intros a b. destruct a, b; reflexivity. Qed.

Theorem absorb_or : forall (a b : Trit),
  trit_or a (trit_and a b) = a.
Proof. intros a b. destruct a, b; reflexivity. Qed.

Theorem and_identity_T : forall (a : Trit),
  trit_and a T = a.
Proof. intros a. destruct a; reflexivity. Qed.

Theorem or_identity_F : forall (a : Trit),
  trit_or a F = a.
Proof. intros a. destruct a; reflexivity. Qed.

(* Kleene 在 {T, F} 子集上等价于 Boole *)
Theorem kleene_extends_boolean : forall (a b : Trit),
  a <> U -> b <> U ->
  (trit_and a b = T <-> (a = T /\ b = T)) /\
  (trit_or a b = F <-> (a = F /\ b = F)).
Proof.
  intros a b Ha Hb.
  destruct a, b; try contradiction;
  unfold trit_and, trit_or;
  tauto.
Qed.

(* 含 U 的 and/or 保持非确定性 *)
Theorem and_preserves_U : forall (a b : Trit),
  (a = U \/ b = U) -> trit_and a b <> T /\ trit_and a b <> F.
Proof.
  intros a b [Hu | Hu]; subst.
  - destruct b; split; discriminate.
  - destruct a; split; discriminate.
Qed.


(* ═══════════════════════════════════════════════════════════
   整数嵌入
   ═══════════════════════════════════════════════════════════ *)

Module TritEmbedding.
  Definition to_int (t : Trit) : Z :=
    match t with
    | T => 1
    | U => 0
    | F => (-1)
    end%Z.

  Definition from_int (n : Z) : option Trit :=
    if Z.eqb n 1 then Some T
    else if Z.eqb n 0 then Some U
    else if Z.eqb n (-1) then Some F
    else None.

  Theorem roundtrip : forall (t : Trit),
    from_int (to_int t) = Some t.
  Proof. intros t. destruct t; reflexivity. Qed.

  Theorem injective : forall (a b : Trit),
    to_int a = to_int b -> a = b.
  Proof. intros a b H. destruct a, b; simpl in H; try discriminate; reflexivity. Qed.
End TritEmbedding.

(* ── 带置信度的三值 ── *)
Record WeightedTrit := mkWeighted {
  value  : Trit;
  confidence : nat;
}.

Definition propagate_confidence (upstream current : WeightedTrit) : nat :=
  (upstream.(confidence) * current.(confidence)) / 100.

Theorem confidence_non_increasing : forall (a b : WeightedTrit),
  a.(confidence) <= 100 -> b.(confidence) <= 100 ->
  propagate_confidence a b <= a.(confidence).
Proof.
  intros a b Ha Hb.
  unfold propagate_confidence.
  destruct a as [va ca], b as [vb cb]. simpl in *.
  lia.
Qed.
