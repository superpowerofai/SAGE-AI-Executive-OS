

def test_task_proposal_requires_approval_before_creating_task(tmp_path):
    store = SageStore(tmp_path / "approvals.db")
    project = store.add_project("Execution project")
    proposal = store.create_task_proposal(
        project, "Contact three prospects", "Direct revenue action", priority=1
    )
    assert store.list_tasks() == []
    assert store.list_task_proposals("pending")[0]["id"] == proposal

    task_id = store.approve_task_proposal(proposal)
    assert store.list_tasks()[0]["id"] == task_id
    approved = store.list_task_proposals("approved")[0]
    assert approved["approved_task_id"] == task_id
    assert approved["status"] == "approved"

    try:
        store.approve_task_proposal(proposal)
        assert False, "approved proposal cannot be approved twice"
    except ValueError as error:
        assert "pending" in str(error)


def test_task_proposal_rejection_does_not_create_task(tmp_path):
    store = SageStore(tmp_path / "rejections.db")
    project = store.add_project("Execution project")
    proposal = store.create_task_proposal(project, "Unapproved action")
    store.reject_task_proposal(proposal)
    assert store.list_tasks() == []
    assert store.list_task_proposals("rejected")[0]["status"] == "rejected"
    try:
        store.reject_task_proposal(proposal)
        assert False, "rejected proposal cannot be rejected twice"
    except ValueError as error:
        assert "pending" in str(error)
