Require Import ZArith.
Open Scope Z_scope.

Definition tag_int (n : Z) : Z := n * 2 + 1.
Definition untag_int (ptr : Z) : Z := ptr / 2.
Definition is_tagged_int (ptr : Z) : bool := Z.odd ptr.

Theorem tag_is_int : forall n : Z, is_tagged_int (tag_int n) = true.
Proof.
  intros n. unfold is_tagged_int, tag_int.
  rewrite Z.odd_add, Z.odd_mul. reflexivity.
Qed.

Theorem heap_ptr_not_int : forall p : Z,
  Z.even p = true -> is_tagged_int p = false.
Proof.
  intros p Heven. unfold is_tagged_int. rewrite Heven. reflexivity.
Qed.

Theorem int_heap_disjoint : forall p : Z,
  is_tagged_int p = true -> negb (Z.odd p) = false.
Proof.
  intros p Hodd. rewrite Hodd. reflexivity.
Qed.

Definition is_valid_obj_type (n : nat) : bool :=
  match n with 1 | 2 | 3 | 4 => true | _ => false end.

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

Theorem cstr_deterministic : forall n1 n2 : nat,
  n1 = n2 -> is_valid_obj_type n1 = is_valid_obj_type n2.
Proof. intros n1 n2 H. subst. reflexivity. Qed.
