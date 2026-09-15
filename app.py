
from flask import Flask, render_template, request, redirect, url_for, flash
from database import (
    init_db,
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    create_query,
    get_query,
    get_open_queries,
    get_resolved_queries,
    get_all_queries,
    update_query_response,
    add_comment,
    get_comments,
    get_category_stats,
    get_high_priority_open,
    get_recurring_tags,
    get_summary_stats,
)

app = Flask(__name__)
app.secret_key = "advisor-query-tracker-secret-key-change-me"


# ── Home Page ─────────────────────────────────────────────────────
@app.route("/")
def index():
    stats = get_summary_stats()
    recent = get_all_queries()[:5]
    return render_template("index.html", stats=stats, recent=recent)


# ── Submit a New Query ────────────────────────────────────────────
@app.route("/submit", methods=["GET", "POST"])
def submit():
    if request.method == "POST":
        submitted_by = request.form.get("submitted_by", "").strip()
        category = request.form.get("category", "")
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        tags = request.form.get("tags", "").strip()

        if not all([submitted_by, category, subject, description]):
            flash("Please fill in all required fields.", "error")
            return render_template("submit.html", categories=CATEGORIES)

        query_id = create_query(submitted_by, category, subject, description, tags)
        flash(f"Query #{query_id} submitted successfully!", "success")
        return redirect(url_for("query_detail", query_id=query_id))

    return render_template("submit.html", categories=CATEGORIES)


# ── Advisor Dashboard ─────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    queries = get_open_queries()
    return render_template("dashboard.html", queries=queries)


# ── Query Detail + Respond ────────────────────────────────────────
@app.route("/query/<int:query_id>", methods=["GET", "POST"])
def query_detail(query_id):
    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "respond":
            advisor_response = request.form.get("advisor_response", "").strip()
            priority = request.form.get("priority", "Medium")
            reference_links = request.form.get("reference_links", "").strip()
            status = request.form.get("status", "In Progress")
            update_query_response(query_id, advisor_response, priority, reference_links, status)
            flash("Query updated successfully!", "success")

        elif action == "comment":
            author = request.form.get("author", "").strip()
            message = request.form.get("message", "").strip()
            if author and message:
                add_comment(query_id, author, message)
                flash("Comment added.", "success")

        return redirect(url_for("query_detail", query_id=query_id))

    q = get_query(query_id)
    if not q:
        flash("Query not found.", "error")
        return redirect(url_for("dashboard"))

    comments = get_comments(query_id)
    return render_template(
        "query_detail.html",
        query=q,
        comments=comments,
        priorities=PRIORITIES,
        statuses=STATUSES,
    )


# ── Knowledge Base ────────────────────────────────────────────────
@app.route("/knowledge")
def knowledge_base():
    category_filter = request.args.get("category", "All")
    search_term = request.args.get("search", "").strip()
    queries = get_resolved_queries(category_filter, search_term)
    return render_template(
        "knowledge_base.html",
        queries=queries,
        categories=CATEGORIES,
        selected_category=category_filter,
        search_term=search_term,
    )


# ── Refresher Reports ────────────────────────────────────────────
@app.route("/refresher")
def refresher():
    stats = get_summary_stats()
    category_stats = get_category_stats()
    high_priority = get_high_priority_open()
    recurring_tags = get_recurring_tags()

    # Build category breakdown dict
    cat_breakdown = {}
    for row in category_stats:
        cat = row["category"]
        if cat not in cat_breakdown:
            cat_breakdown[cat] = {"Open": 0, "In Progress": 0, "Resolved": 0}
        cat_breakdown[cat][row["status"]] = row["cnt"]

    return render_template(
        "refresher.html",
        stats=stats,
        cat_breakdown=cat_breakdown,
        high_priority=high_priority,
        recurring_tags=recurring_tags,
    )


# ── Run ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("\n  ✅ Advisor Query Tracker is running!")
    print("  📍 Open http://localhost:5000 in your browser\n")
    app.run(host='0.0.0.0', port=10000)

