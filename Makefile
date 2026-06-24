.PHONY: worktree worktree-add worktree-rm pr-test-neo pr-test-full pr-test-full-fast \
	build build-backend build-dashboard run run-backend run-dashboard \
	stop stop-backend stop-dashboard clean status quality quality-report

WORKTREE_DIR ?= ../astrbot_worktree
BRANCH ?= $(word 2,$(MAKECMDGOALS))
BASE ?= $(word 3,$(MAKECMDGOALS))
BASE ?= master

RUN_DIR ?= .make
DASHBOARD_DIR ?= dashboard
PS := powershell -NoProfile -ExecutionPolicy Bypass -File
PNPM := npm exec --yes pnpm@10 --
QUALITY_TYPE_TARGETS := astrbot/api astrbot/cli astrbot/core/backup astrbot/core/config astrbot/core/knowledge_base astrbot/core/skills astrbot/utils
QUALITY_SECURITY_TARGETS := astrbot/api astrbot/cli astrbot/core/backup astrbot/core/knowledge_base astrbot/core/skills astrbot/utils

worktree:
	@echo "Usage:"
	@echo "  make worktree-add <branch> [base-branch]"
	@echo "  make worktree-rm  <branch>"

worktree-add:
ifeq ($(strip $(BRANCH)),)
	$(error Branch name required. Usage: make worktree-add <branch> [base-branch])
endif
	@mkdir -p $(WORKTREE_DIR)
	git worktree add $(WORKTREE_DIR)/$(BRANCH) -b $(BRANCH) $(BASE)

worktree-rm:
ifeq ($(strip $(BRANCH)),)
	$(error Branch name required. Usage: make worktree-rm <branch>)
endif
	@if [ -d "$(WORKTREE_DIR)/$(BRANCH)" ]; then \
		git worktree remove $(WORKTREE_DIR)/$(BRANCH); \
	else \
		echo "Worktree $(WORKTREE_DIR)/$(BRANCH) not found."; \
	fi

pr-test-neo:
	./scripts/pr_test_env.sh --profile neo

pr-test-full:
	./scripts/pr_test_env.sh --profile full

pr-test-full-fast:
	./scripts/pr_test_env.sh --profile full --skip-sync --no-dashboard

build: build-backend build-dashboard

build-backend:
	uv sync

build-dashboard:
	cd $(DASHBOARD_DIR) && CI=true $(PNPM) install --no-frozen-lockfile
	cd $(DASHBOARD_DIR) && $(PNPM) build

run: build run-backend run-dashboard status

run-backend:
	@$(PS) scripts/make_dev.ps1 run-backend

run-dashboard:
	@$(PS) scripts/make_dev.ps1 run-dashboard

stop: stop-dashboard stop-backend

stop-backend:
	@$(PS) scripts/make_dev.ps1 stop-backend

stop-dashboard:
	@$(PS) scripts/make_dev.ps1 stop-dashboard

status:
	@$(PS) scripts/make_dev.ps1 status

clean: stop
	@$(PS) scripts/make_dev.ps1 clean

quality:
	uv sync --group dev
	uv run pyright --project pyrightconfig.quality.json
	PYTHONIOENCODING=utf-8 uv run bandit -r $(QUALITY_SECURITY_TARGETS) -c pyproject.toml
	uv run pip-audit
	uv run radon cc $(QUALITY_TYPE_TARGETS) -s -n C
	uv run radon mi $(QUALITY_TYPE_TARGETS) -s

quality-report:
	uv sync --group dev
	uv run pyright
	PYTHONIOENCODING=utf-8 uv run bandit -r astrbot -c pyproject.toml
	uv run pip-audit
	uv run radon cc astrbot -s -n C
	uv run radon mi astrbot -s

# Swallow extra args (branch/base) so make doesn't treat them as targets
%:
	@true
