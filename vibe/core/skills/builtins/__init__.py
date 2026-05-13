from __future__ import annotations

from vibe.core.skills.builtins.commit import SKILL as COMMIT_SKILL
from vibe.core.skills.builtins.init import SKILL as INIT_SKILL
from vibe.core.skills.builtins.pull_request import SKILL as PR_SKILL
from vibe.core.skills.builtins.review import SKILL as REVIEW_SKILL
from vibe.core.skills.builtins.security_review import SKILL as SECURITY_REVIEW_SKILL
from vibe.core.skills.builtins.vibe import SKILL as VIBE_SKILL
from vibe.core.skills.models import SkillInfo

BUILTIN_SKILLS: dict[str, SkillInfo] = {
    skill.name: skill
    for skill in [
        VIBE_SKILL,
        INIT_SKILL,
        REVIEW_SKILL,
        SECURITY_REVIEW_SKILL,
        COMMIT_SKILL,
        PR_SKILL,
    ]
}
