"""测试 DiffApplier —— 验证每种 action 的精确执行"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.diff_applier import DiffApplier
from models.resume import Resume, WorkExperience, Project, Skill, DiffChange, DiffResult, DiffAction


def make_sample_resume():
    return Resume(
        name="张三",
        phone="13800138000",
        email="test@example.com",
        title="Java开发",
        summary="3年Java开发经验",
        work_experiences=[
            WorkExperience(
                company="XX科技",
                position="Java开发工程师",
                start_date="2021-01",
                end_date="2024-01",
                responsibilities=[
                    "负责系统日常维护",
                    "参与需求评审",
                    "编写技术文档",
                ],
                achievements=["完成XX项目上线"],
            ),
        ],
        projects=[
            Project(
                name="电商平台",
                role="后端开发",
                highlights=["使用Spring Boot搭建微服务"],
                tech_stack=["Java", "Spring Boot", "MySQL"],
            ),
        ],
        skills=[
            Skill(category="编程语言", items=["Java", "Python"]),
            Skill(category="框架", items=["Spring Boot"]),
        ],
        certifications=["Java SCJP"],
    )


def test_rewrite_work_responsibility():
    """改写工作经历中的某条职责"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[0]",
            action=DiffAction.rewrite,
            original="负责系统日常维护",
            rewritten="主导XX系统运维，保障99.9%可用性，覆盖日均50万+请求",
            reason="STAR法则量化",
            section_label="工作经历-XX科技-职责1",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert result.work_experiences[0].responsibilities[0] == "主导XX系统运维，保障99.9%可用性，覆盖日均50万+请求"
    assert result.work_experiences[0].responsibilities[1] == "参与需求评审"
    assert result.work_experiences[0].responsibilities[2] == "编写技术文档"


def test_append_to_skills():
    """补充技能"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="skills[0].items",
            action=DiffAction.append,
            item="Golang",
            reason="项目中使用但未在技能列表",
            section_label="技能-编程语言",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "Golang" in result.skills[0].items
    assert "Java" in result.skills[0].items


def test_rewrite_summary():
    """改写Summary"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="summary",
            action=DiffAction.rewrite,
            rewritten="3年Java后端开发经验，专注高并发系统设计与微服务架构",
            reason="调整侧重方向",
            section_label="个人总结",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "高并发" in result.summary


def test_delete_responsibility():
    """删除某条职责"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[2]",
            action=DiffAction.delete,
            reason="冗余表述",
            section_label="工作经历-XX科技-职责3",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert len(result.work_experiences[0].responsibilities) == 2
    assert result.work_experiences[0].responsibilities[0] == "负责系统日常维护"


def test_rewrite_trusts_target_path():
    """改写不再校验原文，信任target路径直接覆写"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[0]",
            action=DiffAction.rewrite,
            original="和原文完全不同的内容也没关系",
            rewritten="新的内容",
            reason="不再校验original字段",
            section_label="...",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert result.work_experiences[0].responsibilities[0] == "新的内容"


def test_rewrite_without_original_still_works():
    """rewrite 不带 original 也能正常工作"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[0]",
            action=DiffAction.rewrite,
            rewritten="直接覆写的内容",
            reason="original字段可选",
            section_label="...",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert result.work_experiences[0].responsibilities[0] == "直接覆写的内容"


def test_index_out_of_range():
    """索引越界产生警告"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[99].responsibilities[0]",
            action=DiffAction.rewrite,
            rewritten="新",
            reason="...",
            section_label="...",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 1
    assert "越界" in warnings[0]


def test_append_to_certifications():
    """补充证书"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="certifications",
            action=DiffAction.append,
            item="AWS Solutions Architect",
            reason="gap分析显示该证加分",
            section_label="证书",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "AWS Solutions Architect" in result.certifications


def test_multiple_changes():
    """多条改动同时应用"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[0]",
            action=DiffAction.rewrite,
            original="负责系统日常维护",
            rewritten="主导系统运维",
            reason="STAR",
            section_label="...",
        ),
        DiffChange(
            target="skills[1].items",
            action=DiffAction.append,
            item="Spring Cloud",
            reason="...",
            section_label="...",
        ),
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "主导系统运维" in result.work_experiences[0].responsibilities[0]
    assert "Spring Cloud" in result.skills[1].items
