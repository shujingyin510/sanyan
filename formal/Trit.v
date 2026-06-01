Inductive Trit : Set := T | F | U.

Definition trit_not (a : Trit) : Trit :=
  match a with T => F | F => T | U => U end.

Definition trit_and (a b : Trit) : Trit :=
  match a, b with
  | T, T => T | F, _ => F | _, F => F | _, _ => U
  end.

Definition trit_or (a b : Trit) : Trit :=
  match a, b with
  | F, F => F | T, _ => T | _, T => T | _, _ => U
  end.

Theorem not_involutive : forall a : Trit, trit_not (trit_not a) = a.
Proof. intros a. destruct a; reflexivity. Qed.

Theorem and_comm : forall a b : Trit, trit_and a b = trit_and b a.
Proof. intros a b. destruct a, b; reflexivity. Qed.

Theorem de_morgan_and : forall a b : Trit,
  trit_not (trit_and a b) = trit_or (trit_not a) (trit_not b).
Proof. intros a b. destruct a, b; reflexivity. Qed.
