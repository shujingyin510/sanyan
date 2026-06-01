(* 三言 形式化验证 — 标记指针编码的内存模型 (Coq 9.0 兼容)

   编码规则:
     整数 n → tagged pointer: 2n + 1
     堆对象 p → pointer: p (LSB=0)
   鉴别:
     整数 ? ptr:  ptr & 1 != 0
     堆对象 ? ptr: ptr & 1 == 0
*)

Require Import ZArith.
Require Import Psatz.
Open Scope Z_scope.

(* ── 值类型 ── *)
Inductive value_type : Set :=
  | IntVal : Z -> value_type
  | HeapPtr : Z -> value_type.

(* ── 标记编码 ── *)
Definition tag_int (n : Z) : Z := n * 2 + 1.
Definition untag_int (ptr : Z) : Z := ptr / 2.
Definition is_tagged_int (ptr : Z) : bool := Z.odd ptr.
Definition is_heap_ptr (ptr : Z) : bool := negb (Z.odd ptr).


(* ═══════════════════════════════════════════════════════════
   往返性质
   ═══════════════════════════════════════════════════════════ *)

Theorem tag_is_int : forall (n : Z),
  is_tagged_int (tag_int n) = true.
Proof.
  intros n. unfold is_tagged_int, tag_int.
  rewrite Z.odd_add. rewrite Z.odd_mul. reflexivity.
Qed.

Theorem untag_tag_roundtrip : forall (n : Z),
  untag_int (tag_int n) = n.
Proof.
  intros n. unfold untag_int, tag_int.
  nia.
Qed.

Theorem heap_ptr_not_int : forall (p : Z),
  Z.even p = true -> is_tagged_int p = false.
Proof.
  intros p Heven. unfold is_tagged_int. rewrite Heven. reflexivity.
Qed.

Theorem int_heap_disjoint : forall (p : Z),
  is_tagged_int p = true -> is_heap_ptr p = false.
Proof.
  intros p Htag. unfold is_heap_ptr. rewrite Htag. reflexivity.
Qed.

(* ── 代数性质 ── *)
Theorem tag_preserves_order : forall (a b : Z),
  a <= b -> tag_int a <= tag_int b.
Proof. intros a b H. unfold tag_int. nia. Qed.

Theorem tag_zero_minimal : forall (n : Z),
  n >= 0 -> tag_int 0 <= tag_int n.
Proof. intros n Hn. apply tag_preserves_order. nia. Qed.

Theorem untag_preserves_sign : forall (n : Z),
  n >= 0 -> untag_int (tag_int n) >= 0.
Proof. intros n Hn. rewrite untag_tag_roundtrip. assumption. Qed.


(* ═══════════════════════════════════════════════════════════
   对象类型校验 — _cstr() 安全性
   ═══════════════════════════════════════════════════════════ *)

Inductive obj_type : Set :=
  | OBJ_STRING
  | OBJ_LIST
  | OBJ_DICT
  | OBJ_FLOAT.

Definition obj_type_to_nat (t : obj_type) : nat :=
  match t with
  | OBJ_STRING => 1
  | OBJ_LIST   => 2
  | OBJ_DICT   => 3
  | OBJ_FLOAT  => 4
  end.

Definition is_valid_obj_type (n : nat) : bool :=
  match n with
  | 1 | 2 | 3 | 4 => true
  | _ => false
  end.

(* 伪正概率上界: 随机 32 位整数恰好 = 1-4 的概率 = 4/2^32 ≈ 10^(-9) *)
Theorem false_positive_bound : forall n : nat,
  is_valid_obj_type n = true -> n <= 4.
Proof.
  intros n H. unfold is_valid_obj_type in H.
  destruct n; try inversion H.
  destruct n; try inversion H.
  destruct n; try inversion H.
  destruct n; try inversion H.
  destruct n; inversion H.
Qed.

(* 确定性 *)
Theorem cstr_deterministic : forall n1 n2 : nat,
  n1 = n2 -> is_valid_obj_type n1 = is_valid_obj_type n2.
Proof. intros n1 n2 H. subst. reflexivity. Qed.
