; ModuleID = '<string>'
source_filename = "<string>"
target datalayout = "e-m:e-p:32:32-i64:64-n32-S128"
target triple = "riscv32-unknown-linux"

@now = external local_unnamed_addr global i64

; Function Attrs: uwtable
define void @__modinit__(i8* nocapture readnone %.1) local_unnamed_addr #0 personality i32 (...)* @__artiq_personality !dbg !5 {
entry:
  %UNN.4.i.i = call i64 @rtio_get_counter() #3, !dbg !9
  %UNN.5.i.i = add i64 %UNN.4.i.i, 125000, !dbg !9
  %now.hi.i.i = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !16
  %now.lo.i.i = load i32, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*), align 8, !dbg !16
  %.14.i.i = zext i32 %now.hi.i.i to i64, !dbg !16
  %.15.i.i = shl nuw i64 %.14.i.i, 32, !dbg !16
  %.16.i.i = zext i32 %now.lo.i.i to i64, !dbg !16
  %.17.i.i = or i64 %.15.i.i, %.16.i.i, !dbg !16
  %UNN.7.i.i = icmp slt i64 %.17.i.i, %UNN.5.i.i, !dbg !16
  br i1 %UNN.7.i.i, label %if.body.i.i, label %_Z50artiq_run_test_subkernel.DMAPulses.simple_self_toozz.exit, !dbg !17

if.body.i.i:                                      ; preds = %entry
  %.20.i.i = lshr i64 %UNN.5.i.i, 32, !dbg !18
  %.21.i.i = trunc i64 %.20.i.i to i32, !dbg !18
  %.22.i.i = trunc i64 %UNN.5.i.i to i32, !dbg !18
  store atomic i32 %.21.i.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !18
  store atomic i32 %.22.i.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !18
  %now.hi.i1.i.pre = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !19
  %.pre = zext i32 %now.hi.i1.i.pre to i64, !dbg !19
  %.pre3 = shl nuw i64 %.pre, 32, !dbg !19
  %.pre4 = zext i32 %.22.i.i to i64, !dbg !19
  %.pre5 = or i64 %.pre3, %.pre4, !dbg !19
  br label %_Z50artiq_run_test_subkernel.DMAPulses.simple_self_toozz.exit, !dbg !18

_Z50artiq_run_test_subkernel.DMAPulses.simple_self_toozz.exit: ; preds = %entry, %if.body.i.i
  %.28.i.i.pre-phi = phi i64 [ %.17.i.i, %entry ], [ %.pre5, %if.body.i.i ], !dbg !19
  %.27.i.i.pre-phi = phi i64 [ %.16.i.i, %entry ], [ %.pre4, %if.body.i.i ], !dbg !19
  %.26.i.i.pre-phi = phi i64 [ %.15.i.i, %entry ], [ %.pre3, %if.body.i.i ], !dbg !19
  %.25.i.i.pre-phi = phi i64 [ %.14.i.i, %entry ], [ %.pre, %if.body.i.i ], !dbg !19
  %now.lo.i2.i = phi i32 [ %now.lo.i.i, %entry ], [ %.22.i.i, %if.body.i.i ], !dbg !19
  %now.hi.i1.i = phi i32 [ %now.hi.i.i, %entry ], [ %now.hi.i1.i.pre, %if.body.i.i ], !dbg !19
  call void @rtio_output(i32 16779520, i32 1), !dbg !23
  %now.new.i.i = add i64 %.28.i.i.pre-phi, 1000000000, !dbg !19
  %.29.i.i = lshr i64 %now.new.i.i, 32, !dbg !19
  %.30.i.i = trunc i64 %.29.i.i to i32, !dbg !19
  %.31.i.i = trunc i64 %now.new.i.i to i32, !dbg !19
  store atomic i32 %.30.i.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !19
  store atomic i32 %.31.i.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !19
  call void @rtio_output(i32 16779520, i32 0), !dbg !28
  ret void, !dbg !32
}

declare i32 @__artiq_personality(...)

; Function Attrs: inaccessiblememonly nounwind
declare i64 @rtio_get_counter() local_unnamed_addr #1

; Function Attrs: inaccessiblememonly
declare void @rtio_output(i32, i32) local_unnamed_addr #2

attributes #0 = { uwtable }
attributes #1 = { inaccessiblememonly nounwind }
attributes #2 = { inaccessiblememonly }
attributes #3 = { nounwind }

!llvm.ident = !{!0}
!llvm.module.flags = !{!1, !2}
!llvm.dbg.cu = !{!3}

!0 = !{!"ARTIQ"}
!1 = !{i32 2, !"Debug Info Version", i32 3}
!2 = !{i32 2, !"Dwarf Version", i32 4}
!3 = distinct !DICompileUnit(language: DW_LANG_Python, file: !4, producer: "ARTIQ", isOptimized: false, runtimeVersion: 0, emissionKind: LineTablesOnly)
!4 = !DIFile(filename: "<synthesized>", directory: "")
!5 = distinct !DISubprogram(name: "__modinit__", linkageName: "__modinit__", scope: !4, file: !4, line: 1, type: !6, scopeLine: 1, spFlags: DISPFlagDefinition, unit: !3, retainedNodes: !8)
!6 = !DISubroutineType(types: !7)
!7 = !{null}
!8 = !{}
!9 = !DILocation(line: 335, column: 18, scope: !10, inlinedAt: !12)
!10 = distinct !DISubprogram(name: "_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz", linkageName: "_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz", scope: !11, file: !11, line: 329, type: !6, scopeLine: 329, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!11 = !DIFile(filename: "core.py", directory: "/home/spaqin/m-labs/artiq/artiq/coredevice")
!12 = distinct !DILocation(line: 31, column: 8, scope: !13, inlinedAt: !15)
!13 = distinct !DISubprogram(name: "_Z50artiq_run_test_subkernel.DMAPulses.simple_self_toozz", linkageName: "_Z50artiq_run_test_subkernel.DMAPulses.simple_self_toozz", scope: !14, file: !14, line: 30, type: !6, scopeLine: 30, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!14 = !DIFile(filename: "test_subkernel.py", directory: "")
!15 = distinct !DILocation(line: 1, scope: !5)
!16 = !DILocation(line: 336, column: 11, scope: !10, inlinedAt: !12)
!17 = !DILocation(line: 336, column: 8, scope: !10, inlinedAt: !12)
!18 = !DILocation(line: 337, column: 12, scope: !10, inlinedAt: !12)
!19 = !DILocation(line: 84, column: 8, scope: !20, inlinedAt: !22)
!20 = distinct !DISubprogram(name: "_Z33artiq.coredevice.ttl.TTLOut.pulseI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z33artiq.coredevice.ttl.TTLOut.pulseI27artiq.coredevice.ttl.TTLOutEzz", scope: !21, file: !21, line: 78, type: !6, scopeLine: 78, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!21 = !DIFile(filename: "ttl.py", directory: "/home/spaqin/m-labs/artiq/artiq/coredevice")
!22 = distinct !DILocation(line: 32, column: 8, scope: !13, inlinedAt: !15)
!23 = !DILocation(line: 49, column: 8, scope: !24, inlinedAt: !25)
!24 = distinct !DISubprogram(name: "_Z33artiq.coredevice.ttl.TTLOut.set_oI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z33artiq.coredevice.ttl.TTLOut.set_oI27artiq.coredevice.ttl.TTLOutEzz", scope: !21, file: !21, line: 48, type: !6, scopeLine: 48, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!25 = distinct !DILocation(line: 57, column: 8, scope: !26, inlinedAt: !27)
!26 = distinct !DISubprogram(name: "_Z30artiq.coredevice.ttl.TTLOut.onI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z30artiq.coredevice.ttl.TTLOut.onI27artiq.coredevice.ttl.TTLOutEzz", scope: !21, file: !21, line: 52, type: !6, scopeLine: 52, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!27 = distinct !DILocation(line: 83, column: 8, scope: !20, inlinedAt: !22)
!28 = !DILocation(line: 49, column: 8, scope: !24, inlinedAt: !29)
!29 = distinct !DILocation(line: 65, column: 8, scope: !30, inlinedAt: !31)
!30 = distinct !DISubprogram(name: "_Z31artiq.coredevice.ttl.TTLOut.offI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z31artiq.coredevice.ttl.TTLOut.offI27artiq.coredevice.ttl.TTLOutEzz", scope: !21, file: !21, line: 60, type: !6, scopeLine: 60, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!31 = distinct !DILocation(line: 85, column: 8, scope: !20, inlinedAt: !22)
!32 = !DILocation(line: 1, scope: !5)
