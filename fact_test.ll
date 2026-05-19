; ModuleID = "fact"
target triple = "x86_64-pc-linux-gnu"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

define i8* @"阶乘"(i8* %"n")
{
entry:
  %"n.1" = alloca i8*
  store i8* %"n", i8** %"n.1"
  br label %"if_test"
if_merge:
  %"n.3" = load i8*, i8** %"n.1"
  %"unbox.3" = ptrtoint i8* %"n.3" to i32
  %"n.4" = load i8*, i8** %"n.1"
  %"unbox.4" = ptrtoint i8* %"n.4" to i32
  %"box.3" = inttoptr i32 1 to i8*
  %"unbox.5" = ptrtoint i8* %"box.3" to i32
  %"减_tmp" = sub i32 %"unbox.4", %"unbox.5"
  %"box.4" = inttoptr i32 %"减_tmp" to i8*
  %"call_阶乘" = call i8* @"阶乘"(i8* %"box.4")
  %"unbox.6" = ptrtoint i8* %"call_阶乘" to i32
  %"乘_tmp" = mul i32 %"unbox.3", %"unbox.6"
  %"box.5" = inttoptr i32 %"乘_tmp" to i8*
  ret i8* %"box.5"
if_test:
  %"n.2" = load i8*, i8** %"n.1"
  %"unbox" = ptrtoint i8* %"n.2" to i32
  %"box" = inttoptr i32 2 to i8*
  %"unbox.1" = ptrtoint i8* %"box" to i32
  %"小于_tmp" = icmp slt i32 %"unbox", %"unbox.1"
  %"小于_bool" = zext i1 %"小于_tmp" to i32
  %"box.1" = inttoptr i32 %"小于_bool" to i8*
  %"unbox.2" = ptrtoint i8* %"box.1" to i32
  %"if_cond" = icmp ne i32 %"unbox.2", 0
  br i1 %"if_cond", label %"if_body", label %"if_next"
if_body:
  %"box.2" = inttoptr i32 1 to i8*
  ret i8* %"box.2"
if_next:
  br label %"if_merge"
}

define i8* @"main"()
{
entry:
  %"box" = inttoptr i32 5 to i8*
  %"call_阶乘" = call i8* @"阶乘"(i8* %"box")
  %"r" = alloca i8*
  store i8* %"call_阶乘", i8** %"r"
  %"r.1" = load i8*, i8** %"r"
  %".3" = getelementptr inbounds [4 x i8], [4 x i8]* @".str.3", i32 0, i32 0
  %"unbox" = ptrtoint i8* %"r.1" to i32
  %".4" = call i32 (i8*, ...) @"printf"(i8* %".3", i32 %"unbox")
  ret i8* null
}

@".str.3" = private constant [4 x i8] c"%d\0a\00"