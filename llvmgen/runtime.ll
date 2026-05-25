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
  br label %scan
scan:
  %_si = phi i32 [ 0, %entry ], [ %_ni, %scan ]
  %_sp = getelementptr inbounds i8, i8* %str, i32 %_si
  %_sc = load i8, i8* %_sp
  %_sd = icmp eq i8 %_sc, 0
  %_ni = add i32 %_si, 1
  br i1 %_sd, label %write, label %scan
write:
  call void @san_sys_write(i32 1, i8* %str, i32 %_si)
  ret void
}

; ── 列表运行时 ──
; 列表布局: [items:i8*][len:i32][cap:i32] = 16 bytes
declare i8* @_rt_malloc(i32)
declare void @_rt_free(i8*)

define i8* @rt_list_new() {
  %_p = call i8* @_rt_malloc(i32 16)
  ; items = null (already zero from HeapAlloc)
  ; len = 0, cap = 0
  ret i8* %_p
}

define void @rt_list_push_item(i8* %lst, i8* %item) {
entry:
  ; load len and cap
  %_lenp = getelementptr inbounds i8, i8* %lst, i32 8
  %_len = load i32, i32* %_lenp
  %_capp = getelementptr inbounds i8, i8* %lst, i32 12
  %_cap = load i32, i32* %_capp
  %_full = icmp sge i32 %_len, %_cap
  br i1 %_full, label %grow, label %append

grow:
  %_ncap = add i32 %_cap, 8
  %_nsize = mul i32 %_ncap, 8
  %_nitems = call i8* @_rt_malloc(i32 %_nsize)
  ; copy old items
  %_oldp = bitcast i8* %lst to i8**
  %_old = load i8*, i8** %_oldp
  %_cp = icmp ne i8* %_old, null
  br i1 %_cp, label %copy, label %set_items

copy:
  %_i = phi i32 [ 0, %grow ], [ %_ni, %copy ]
  %_src = getelementptr inbounds i8*, i8** %_old, i32 %_i
  %_dst = getelementptr inbounds i8*, i8** %_nitems, i32 %_i
  %_v = load i8*, i8** %_src
  store i8* %_v, i8** %_dst
  %_ni = add i32 %_i, 1
  %_cd = icmp slt i32 %_ni, %_len
  br i1 %_cd, label %copy, label %free_old

free_old:
  call void @_rt_free(i8* %_old)
  br label %set_items

set_items:
  store i8* %_nitems, i8** %_oldp
  store i32 %_ncap, i32* %_capp
  br label %append

append:
  %_ip = bitcast i8* %lst to i8**
  %_items = load i8*, i8** %_ip
  %_di = getelementptr inbounds i8*, i8** %_items, i32 %_len
  store i8* %item, i8** %_di
  %_nlen = add i32 %_len, 1
  store i32 %_nlen, i32* %_lenp
  ret void
}

define i32 @rt_list_len(i8* %lst) {
  %_p = getelementptr inbounds i8, i8* %lst, i32 8
  %_len = load i32, i32* %_p
  ret i32 %_len
}

define i8* @rt_list_get(i8* %lst, i32 %idx) {
  %_ip = bitcast i8* %lst to i8**
  %_items = load i8*, i8** %_ip
  %_p = getelementptr inbounds i8*, i8** %_items, i32 %idx
  %_v = load i8*, i8** %_p
  ret i8* %_v
}
