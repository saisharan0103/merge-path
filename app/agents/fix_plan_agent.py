from dataclasses import dataclass


@dataclass
class FixPlan:
    summary: str
    steps: list[str]


class FixPlanAgent:
    def generate(self, issue_context: str, repo_scan: str) -> FixPlan:
        return FixPlan(
            summary="Fix planning is not implemented yet.",
            steps=[f"Review issue context: {issue_context}", f"Review repo scan: {repo_scan}"],
        )
