import os


os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

from paper_ai_reader.gui.app import main


if __name__ == "__main__":
    main()
