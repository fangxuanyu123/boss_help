"""评测金标准数据集 —— 简历+岗位 → 人工标注的理想改动"""
from models.job import JobRequirement

CASES = [
    {
        "id": "case_01_java_senior",
        "resume_text": """
姓名: 张三
电话: 138xxxx
求职意向: Java开发工程师

工作经历:
- XX科技 | Java开发 (2021.01 - 2024.01)
  负责系统日常维护
  参与需求评审和方案设计
  编写技术文档和接口文档

项目经历:
- 电商平台 | 后端开发
  负责订单模块开发
  使用Spring Boot框架
  数据库使用MySQL

技能:
- 编程语言: Java, Python
- 框架: Spring Boot, MyBatis
- 数据库: MySQL
""",
        "job_title": "高级Java开发工程师",
        "job": JobRequirement(
            title="高级Java开发工程师",
            level="高级",
            industry="互联网",
            responsibilities=[
                "负责核心业务系统架构设计和性能优化",
                "参与微服务架构演进和高可用方案设计",
                "编写高质量代码，保障系统稳定性和可扩展性",
            ],
            requirements=[
                "3年以上Java开发经验",
                "熟练掌握Spring Cloud微服务体系",
                "熟悉分布式系统设计，有高并发经验",
                "熟悉MySQL优化和Redis缓存策略",
            ],
            tech_keywords=["Java", "Spring Cloud", "微服务", "分布式", "MySQL", "Redis", "Kafka"],
            soft_skills=["团队协作", "技术方案设计"],
            source="title",
        ),
        "expected": {
            "min_changes": 3,
            "max_changes": 12,
            "must_contain_actions": ["rewrite", "append"],  # 至少要有这两类改动
            "must_cover_sections": ["work_experiences", "skills"],  # 至少覆盖这些板块
            "key_terms_in_changes": ["量化", "STAR", "优化"],  # reason中应出现的词
            "quality_checks": [
                "每条改动reason必须具体，不能只是'优化表述'",
                "不能编造新的项目名或公司名",
                "append的item应该来自job的tech_keywords",
            ],
        },
    },
    {
        "id": "case_02_python_ml",
        "resume_text": """
姓名: 李四
电话: 139xxxx
求职意向: Python开发工程师

工作经历:
- YY数据 | Python开发 (2022.03 - 2025.03)
  负责数据处理脚本编写
  使用Pandas进行数据分析
  参与ETL流程维护

项目经历:
- 用户画像系统 | 数据开发
  使用Python进行特征工程
  搭建简单的Flask API服务

技能:
- 编程语言: Python
- 框架: Flask, Django
- 工具: Pandas, Git
""",
        "job_title": "Python后端开发工程师",
        "job": JobRequirement(
            title="Python后端开发工程师",
            level="中级",
            industry="互联网",
            responsibilities=[
                "设计和开发高性能后端API服务",
                "参与数据管道和推荐系统建设",
                "优化系统性能和代码质量",
            ],
            requirements=[
                "2年以上Python后端开发经验",
                "熟悉FastAPI或Django REST框架",
                "有数据处理和SQL优化经验",
                "了解Redis、消息队列等中间件",
            ],
            tech_keywords=["Python", "FastAPI", "Django", "Redis", "Celery", "PostgreSQL", "Docker"],
            soft_skills=["逻辑思维", "沟通能力"],
            source="title",
        ),
        "expected": {
            "min_changes": 3,
            "max_changes": 12,
            "must_contain_actions": ["rewrite", "append"],
            "must_cover_sections": ["work_experiences", "skills", "projects"],
            "key_terms_in_changes": ["量化", "技术栈", "成果"],
            "quality_checks": [
                "Flask/Django经验应该被STAR法则改写得更具体",
                "技能列表应该补充Redis、Docker等岗位要求但简历缺失的关键词",
                "不能编造不存在的工作经历",
            ],
        },
    },
    {
        "id": "case_03_embedded_cpp",
        "resume_text": """
姓名: 王五
电话: 137xxxx
求职意向: 嵌入式软件开发工程师

工作经历:
- ZZ电子 | 嵌入式开发 (2020.07 - 2024.12)
  负责MCU固件开发
  参与硬件调试和测试
  编写技术文档

项目经历:
- 智能门锁系统 | 嵌入式开发
  基于STM32开发门锁控制程序
  实现指纹识别模块集成

技能:
- 编程语言: C, C++
- 平台: STM32, FreeRTOS
- 工具: Keil, Git
""",
        "job_title": "嵌入式软件工程师",
        "job": JobRequirement(
            title="嵌入式软件工程师",
            level="中级",
            industry="智能硬件",
            responsibilities=[
                "负责嵌入式系统固件开发和调试",
                "参与RTOS移植和驱动开发",
                "优化系统功耗和实时性能",
            ],
            requirements=[
                "2年以上嵌入式开发经验",
                "精通C/C++，熟悉RTOS原理",
                "有ARM Cortex-M系列开发经验",
                "了解常用通信协议（I2C/SPI/UART/CAN）",
            ],
            tech_keywords=["C", "C++", "RTOS", "ARM", "STM32", "I2C", "SPI", "UART", "CAN", "Linux"],
            soft_skills=["问题排查", "文档编写"],
            source="title",
        ),
        "expected": {
            "min_changes": 2,
            "max_changes": 10,
            "must_contain_actions": ["rewrite", "append"],
            "must_cover_sections": ["work_experiences", "skills"],
            "key_terms_in_changes": ["具体", "量化", "补充"],
            "quality_checks": [
                "RTOS和通信协议经验应该被显式提及",
                "技能列表应该补充CAN/Linux等关键词",
                "工作经历中的'负责MCU固件开发'需要更具体的描述",
            ],
        },
    },
]
