import { afterEach, describe, expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import ProjectList from '@/components/chat/ProjectList.vue';
import ToolCallItem from '@/components/chat/message_list_comps/ToolCallItem.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

describe('chat interaction smokes', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('expands ProjectList and emits actions without transition warnings', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const confirmSpy = vi.fn(async () => true);

    const wrapper = mountWithVuetify(ProjectList, {
      props: {
        initialExpanded: false,
        selectedProjectId: 'project-1',
        projects: [
          {
            project_id: 'project-1',
            title: 'Inbox',
            emoji: '📁',
            created_at: '2026-06-30T00:00:00Z',
            updated_at: '2026-06-30T00:00:00Z',
          },
        ],
      },
      global: {
        provide: {
          $confirm: confirmSpy,
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('.project-list-wrap').isVisible()).toBe(false);

    await wrapper.find('.project-btn').trigger('click');
    await flushPromises();

    expect(wrapper.find('.project-list-wrap').isVisible()).toBe(true);
    expect(wrapper.text()).toContain('Inbox');

    await wrapper.find('.create-project-item').trigger('click');
    expect(wrapper.emitted('createProject')).toHaveLength(1);

    await wrapper.find('.project-item').trigger('click');
    expect(wrapper.emitted('selectProject')?.[0]).toEqual(['project-1']);

    await wrapper.find('.edit-project-btn').trigger('click');
    expect(wrapper.emitted('editProject')).toHaveLength(1);

    await wrapper.find('.delete-project-btn').trigger('click');
    await flushPromises();
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(wrapper.emitted('deleteProject')?.[0]).toEqual(['project-1']);

    expect(
      warnSpy.mock.calls.some((args) =>
        args.some((arg) =>
          String(arg).includes(
            'Component inside <Transition> renders non-element root node',
          ),
        ),
      ),
    ).toBe(false);
  });

  it('toggles ToolCallItem inline details without transition warnings', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const wrapper = mountWithVuetify(ToolCallItem, {
      props: {
        isDark: true,
      },
      slots: {
        label: '<span class="tool-call-label">Run tool</span>',
        details: '<div class="tool-call-details-content">Tool output</div>',
      },
    });

    await flushPromises();

    expect(wrapper.find('.tool-call-details-content').exists()).toBe(false);

    await wrapper.find('.tool-call-line').trigger('click');
    await flushPromises();

    expect(wrapper.find('.tool-call-details-content').text()).toBe(
      'Tool output',
    );
    expect(wrapper.find('.tool-call-inline-details').classes()).toContain(
      'is-dark',
    );

    await wrapper.find('.tool-call-line').trigger('keydown.space');
    await flushPromises();
    expect(wrapper.find('.tool-call-details-content').exists()).toBe(false);

    expect(
      warnSpy.mock.calls.some((args) =>
        args.some((arg) =>
          String(arg).includes(
            'Component inside <Transition> renders non-element root node',
          ),
        ),
      ),
    ).toBe(false);
  });
});
