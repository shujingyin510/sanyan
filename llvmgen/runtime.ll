; runtime.ll — SanYan 运行时（手写 LLVM IR）

declare void @san_sys_write(i32, i8*, i32)

@_rt_buf = global [22 x i8] zeroinitializer

define void @rt_print_int(i64 %tagged) {
entry:
  %_r0 = ashr i64 %tagged, 1
  %_r1 = icmp slt i64 %_r0, 0
  %_r2 = sub i64 0, %_r0
  %_r3 = select i1 %_r1, i64 %_r2, i64 %_r0
  br i1 %_r1, label %put_sign, label %build

put_sign:
  %_s0 = getelementptr inbounds [22 x i8], [22 x i8]* @_rt_buf, i64 0, i32 0
  store i8 45, i8* %_s0
  br label %build

build:
  %_off = phi i32 [ 1, %put_sign ], [ 0, %entry ]
  br label %loop

loop:
  %_i = phi i32 [ %_off, %build ], [ %_ni, %loop ]
  %_v = phi i64 [ %_r3, %build ], [ %_nv, %loop ]
  %_p = getelementptr inbounds [22 x i8], [22 x i8]* @_rt_buf, i64 0, i32 %_i
  %_d = urem i64 %_v, 10
  %_c64 = add i64 %_d, 48
  %_c = trunc i64 %_c64 to i8
  store i8 %_c, i8* %_p
  %_nv = udiv i64 %_v, 10
  %_ni = add i32 %_i, 1
  %_ld = icmp eq i64 %_nv, 0
  br i1 %_ld, label %exit, label %loop

exit:
  %_ei = phi i32 [ %_ni, %loop ]
  %_nl = getelementptr inbounds [22 x i8], [22 x i8]* @_rt_buf, i64 0, i32 %_ei
  store i8 10, i8* %_nl
  %_re = sub i32 %_ei, 1
  br label %rev_loop

rev_loop:
  %_l = phi i32 [ %_off, %exit ], [ %_nl2, %rev_swap ]
  %_r = phi i32 [ %_re, %exit ], [ %_nr2, %rev_swap ]
  %_rd = icmp sge i32 %_l, %_r
  br i1 %_rd, label %done, label %rev_swap

rev_swap:
  %_lp = getelementptr inbounds [22 x i8], [22 x i8]* @_rt_buf, i64 0, i32 %_l
  %_rp = getelementptr inbounds [22 x i8], [22 x i8]* @_rt_buf, i64 0, i32 %_r
  %_lc = load i8, i8* %_lp
  %_rc = load i8, i8* %_rp
  store i8 %_rc, i8* %_lp
  store i8 %_lc, i8* %_rp
  %_nl2 = add i32 %_l, 1
  %_nr2 = sub i32 %_r, 1
  br label %rev_loop

done:
  %_tl = add i32 %_ei, 1
  %_sp = getelementptr inbounds [22 x i8], [22 x i8]* @_rt_buf, i64 0, i32 %_off
  call void @san_sys_write(i32 1, i8* %_sp, i32 %_tl)
  ret void
}

define void @rt_print_str(i8* %str) {
entry:
  ret void
}
