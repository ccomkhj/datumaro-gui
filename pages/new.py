import streamlit as st
import datumaro as dm
from datumaro.components.dataset import Dataset
from datumaro.components.hl_ops import HLOps
import datumaro.plugins.splitter as splitter
from utils import save_uploaded_files, upload_to_s3
import os


def create_new_task(input_base_path: str, now: str, export_base_path="exported"):
    # Load new dataset
    dataset = Dataset.import_from(input_base_path, "coco")

    # Aggregate subsets
    aggregated = HLOps.aggregate(dataset, from_subsets=["default"], to_subset="default")

    # Split the aggregated dataset
    splits = [("train", 0.8), ("val", 0.2)]
    task = splitter.SplitTask.detection.name
    resplitted = aggregated.transform("split", task=task, splits=splits)

    export_path = os.path.join(export_base_path, now)

    # Export the split datasets
    resplitted.export(export_path, "coco", save_media=True)

    return export_path


def main():
    st.write("# Register Annotation")
    images = st.file_uploader(
        "Upload Image Files", accept_multiple_files=True, type=["jpg", "png"]
    )
    annotation = st.file_uploader("Upload Annotation File", type=["json", "xml"])

    if "task_path" not in st.session_state:
        st.session_state.task_path = None
    if "s3_uri" not in st.session_state:
        st.session_state.s3_uri = ""

    if st.button("Register Annotation"):
        if images and annotation:
            base_path, now = save_uploaded_files(images, annotation)
            task_path = create_new_task(base_path, now)
            st.session_state.task_path = task_path
            st.success(f"New task created and dataset split. Data saved at {task_path}")

    if st.session_state.task_path is not None:
        st.session_state.s3_uri = st.text_input(
            "Enter S3 URI to upload (e.g., s3://hexa-cv-dataset/test/)",
            st.session_state.s3_uri,
        )

        if st.button("Upload to S3"):
            if st.session_state.task_path is None:
                st.warning("First create a task before uploading to S3.")
            elif not st.session_state.s3_uri:
                st.warning("Write S3 URI.")
            else:
                upload_to_s3(st.session_state.task_path, st.session_state.s3_uri)
                st.success(f"Data uploaded to S3 at {st.session_state.s3_uri}")


main()