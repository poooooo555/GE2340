from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from config import DEEPSEEK_API_KEY
from services.deepseek_service import analyze_images
from services.image_service import cleanup_files, save_uploads

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@main_bp.route("/analyze", methods=["POST"])
def analyze():
    #send the image to the ai analyze
    files = [f for f in request.files.getlist("images") if f and f.filename]
    labels = request.form.getlist("labels")

    if not files:
        flash("Please select at least one image.")
        return redirect(url_for("main.index"))

    if not DEEPSEEK_API_KEY:
        flash("DEEPSEEK_API_KEY is not set. Please configure it before uploading.")
        return redirect(url_for("main.index"))

    saved_items = []

    try:
        saved_items = save_uploads(files, labels)

        if not saved_items:
            flash("No valid JPG/PNG images were uploaded.")
            return redirect(url_for("main.index"))

        # saved_items is a list of (label, path) tuples
        # just for ai to know the name of a file identification relationship
        schedule = analyze_images(saved_items)

    except Exception as exc:
        current_app.logger.exception("Analysis failed")
        flash(f"Analysis failed: {exc}")
        return redirect(url_for("main.index"))

    finally:
        cleanup_files(saved_items)

    return render_template("timetable.html", schedule=schedule)