"""Evolution Dashboard — 进化仪表盘"""


class EvolutionDashboard:
    """进化仪表盘：可视化进化状态"""

    def __init__(self, patch_history=None, benchmark=None, reviewer=None):
        from agent_review import PatchHistory, ReviewerAgent

        self.patch_history = patch_history or PatchHistory()
        self.benchmark = benchmark
        self.reviewer = reviewer or ReviewerAgent()

    def render(self) -> str:
        """渲染仪表盘"""
        analytics = self.patch_history.get_analytics()
        review_stats = self.reviewer.get_stats()

        lines = [
            '╔══════════════════════════════════════════════════════╗',
            '║          Evolution Dashboard                        ║',
            '╠══════════════════════════════════════════════════════╣',
            f'║  总补丁数:     {analytics["total_patches"]:40d}║',
            f'║  成功:         {analytics["success_count"]:40d}║',
            f'║  回滚:         {analytics["rollback_count"]:40d}║',
            f'║  成功率:       {analytics["success_rate"]:.1%}{" " * 37}║',
            f'║  回滚率:       {analytics["rollback_rate"]:.1%}{" " * 37}║',
            '╠══════════════════════════════════════════════════════╣',
            f'║  加权提升:     {analytics["avg_speedup"]:.1f}% (含可信度权重){" " * 18}║',
            f'║  原始提升:     {analytics.get("raw_avg_speedup", 0):.1f}% (未加权){" " * 22}║',
            f'║  平均内存变化: {analytics["avg_memory_delta"]:.1f}KB{" " * 34}║',
            f'║  总测试数:     {analytics["total_tests_run"]:40d}║',
            f'║  新生成测试:   {analytics["total_new_tests"]:40d}║',
            f'║  本周补丁:     {analytics["week_patches"]:40d}║',
            '╠══════════════════════════════════════════════════════╣',
            '║  审查统计                                          ║',
            f'║  总审查:       {review_stats["total"]:40d}║',
            f'║  通过:         {review_stats.get("approve", 0):40d}║',
            f'║  拒绝:         {review_stats.get("reject", 0):40d}║',
            '╠══════════════════════════════════════════════════════╣',
            '║  Top 模式 (按成功率)                               ║',
        ]

        top_patterns = self.patch_history.get_top_patterns('success_rate', 5)
        for p in top_patterns:
            name = f'{p["target"]}:{p["opt_type"]}'
            rate = f'{p["success_rate"]:.0%}'
            speedup = f'+{p["avg_speedup"]:.1f}%' if p['avg_speedup'] > 0 else '0%'
            lines.append(f'║    {name:25s} {rate:6s} {speedup:10s}        ║')

        lines.extend(
            [
                '╚══════════════════════════════════════════════════════╝',
            ]
        )

        return '\n'.join(lines)
