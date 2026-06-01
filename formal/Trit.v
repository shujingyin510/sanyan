(* 三言 形式化验证 — 三值逻辑公理化

   Trit.v: Kleene 三值逻辑核心定义与定理。
   这是 Vellvm 验证的规范层：所有 LLVM IR 级别的三值操作
   必须满足这里定义的代数定律。

   三值系统: {T (真), F (假), U (未知/可能)}
   Kleene 语义:
     T ∧ F = F    T ∨ F = T    ¬T = F
     T ∧ U = U    T ∨ U = T    ¬F = T
     F ∧ U = F    F ∨ U = U    ¬U = U
*)

From Coq Require Import Lia.

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

(* ── 蕴含 (Kleene →) ── *)

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

(* ── 双重否定消除: ¬¬a = a ── *)
Theorem not_involutive : forall (a : Trit),
  trit_not (trit_not a) = a.
Proof.
  intros a. destruct a; reflexivity.
Qed.

(* ── 交换律 ── *)
Theorem and_comm : forall (a b : Trit),
  trit_and a b = trit_and b a.
Proof.
  intros a b. destruct a, b; reflexivity.
Qed.

Theorem or_comm : forall (a b : Trit),
  trit_or a b = trit_or b a.
Proof.
  intros a b. destruct a, b; reflexivity.
Qed.

(* ── 结合律 ── *)
Theorem and_assoc : forall (a b c : Trit),
  trit_and a (trit_and b c) = trit_and (trit_and a b) c.
Proof.
  intros a b c. destruct a, b, c; reflexivity.
Qed.

Theorem or_assoc : forall (a b c : Trit),
  trit_or a (trit_or b c) = trit_or (trit_or a b) c.
Proof.
  intros a b c. destruct a, b, c; reflexivity.
Qed.

(* ── 幂等律 ── *)
Theorem and_idempotent : forall (a : Trit),
  trit_and a a = a.
Proof.
  intros a. destruct a; reflexivity.
Qed.

Theorem or_idempotent : forall (a : Trit),
  trit_or a a = a.
Proof.
  intros a. destruct a; reflexivity.
Qed.

(* ── De Morgan 定律 ──
   注意: Kleene 逻辑中 De Morgan 需要特殊处理 U。
   ¬(a ∧ b) = ¬a ∨ ¬b  对 T/F 成立，U 亦成立。
   ¬(a ∨ b) = ¬a ∧ ¬b  对 T/F 成立，U 亦成立。
*)
Theorem de_morgan_and : forall (a b : Trit),
  trit_not (trit_and a b) = trit_or (trit_not a) (trit_not b).
Proof.
  intros a b. destruct a, b; reflexivity.
Qed.

Theorem de_morgan_or : forall (a b : Trit),
  trit_not (trit_or a b) = trit_and (trit_not a) (trit_not b).
Proof.
  intros a b. destruct a, b; reflexivity.
Qed.

(* ── 吸收律 ── *)
Theorem absorb_and : forall (a b : Trit),
  trit_and a (trit_or a b) = a.
Proof.
  intros a b. destruct a, b; reflexivity.
Qed.

Theorem absorb_or : forall (a b : Trit),
  trit_or a (trit_and a b) = a.
Proof.
  intros a b. destruct a, b; reflexivity.
Qed.

(* ── U 是 and/or 的 identity? ──
   在 Kleene 逻辑中: T ∧ U = U, F ∧ U = F, U ∧ U = U
   所以 U 不是 and 的 identity。
   但 U ∨ F = U, U ∨ T = T, U ∨ U = U.
   同样 U 也不是 or 的 identity。
   这区别于 Boole 逻辑。
*)

(* ── T 是 and 的 identity, F 是 or 的 identity ── *)
Theorem and_identity_T : forall (a : Trit),
  trit_and a T = a.
Proof.
  intros a. destruct a; reflexivity.
Qed.

Theorem or_identity_F : forall (a : Trit),
  trit_or a F = a.
Proof.
  intros a. destruct a; reflexivity.
Qed.

(* ── 与 Boole 逻辑的兼容性: 在 {T, F} 子集上等价于 Boole ── *)
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

(* ── 唯一 U 保留性质: 任何含 U 的 and/or 保持 U ── *)
Theorem and_preserves_U : forall (a b : Trit),
  (a = U \/ b = U) -> trit_and a b <> T /\ trit_and a b <> F.
Proof.
  intros a b [Hu | Hu]; subst; destruct (if Hu then a else b); split; discriminate.
Qed.


(* ═══════════════════════════════════════════════════════════
   到整数的嵌入 (用于与 LLVM (-1, 0, 1) 表示对齐)
   ═══════════════════════════════════════════════════════════ *)

Module TritEmbedding.
  (* T → 1, U → 0, F → -1 *)
  Definition to_int (t : Trit) : Z :=
    match t with
    | T => 1
    | U => 0
    | F => (-1)%Z
    end.

  Definition from_int (n : Z) : option Trit :=
    if Z.eqb n 1 then Some T
    else if Z.eqb n 0 then Some U
    else if Z.eqb n (-1) then Some F
    else None.

  Theorem roundtrip : forall (t : Trit),
    from_int (to_int t) = Some t.
  Proof.
    intros t. destruct t; reflexivity.
  Qed.

  Theorem injective : forall (a b : Trit),
    to_int a = to_int b -> a = b.
  Proof.
    intros a b H. destruct a, b; simpl in H; try discriminate; reflexivity.
  Qed.
End TritEmbedding.

(* ── 带置信度的三值（概率三态）── *)
Record WeightedTrit := mkWeighted {
  value  : Trit;
  confidence : nat;  (* 0-100 的置信度 *)
}.

(* 置信度传播: 上游 × 当前 → 传播后置信度 *)
Definition propagate_confidence (upstream current : WeightedTrit) : nat :=
  (upstream.(confidence) * current.(confidence)) / 100.

(* 5 态映射到 3 值后，置信度必须单调不减 *)
Theorem confidence_non_increasing : forall (a b : WeightedTrit),
  a.(confidence) <= 100 -> b.(confidence) <= 100 ->
  propagate_confidence a b <= a.(confidence).
Proof.
  intros a b Ha Hb.
  unfold propagate_confidence.
  destruct a as [va ca], b as [vb cb]. simpl in *.
  lia.
Qed.
