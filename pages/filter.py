import streamlit as st
import datumaro as dm
from datumaro.components.dataset import Dataset
from datumaro.components.annotation import Annotation, Bbox
from datumaro.components.dataset_base import DatasetItem
from datumaro.components.media import Image
from datumaro.components.hl_ops import HLOps
import datumaro.plugins.splitter as splitter
from utils import save_uploaded_files, upload_to_s3, show_category_statistics
import os
import json


def create_new_task_filter(
    input_base_path: str,
    now: str,
    filter_cmd: str,
    export_base_path="exported",
    split_option=True,
):
    # Load new dataset
    dataset = Dataset.import_from(input_base_path, "coco_instances")

    st.text("Dataset profile before filtering:")
    st.code(dataset)

    # Define the filter function in the current scope
    exec(filter_cmd, globals())

    # Use the dynamically created filter function
    filtered_result = Dataset.filter(dataset, globals()["filter_func"])

    st.text("Dataset profile after filtering:")
    st.code(filtered_result)
    
    # Create a temporary export for statistics before splitting
    temp_export_path = os.path.join(export_base_path, f"{now}_temp")
    os.makedirs(temp_export_path, exist_ok=True)
    
    # Export the filtered dataset for statistics
    filtered_result.export(temp_export_path, "coco_instances", save_media=False)
    
    # Get the annotation file path for statistics
    stats_annotations_path = os.path.join(temp_export_path, "annotations", "instances_default.json")
    
    # Now prepare the actual export with splitting if needed
    export_path = os.path.join(export_base_path, now)
    
    if split_option:
        # Split the filtered dataset
        splits = [("train", 0.8), ("val", 0.2)]
        filtered_result = filtered_result.transform("random_split", splits=splits)

    # Export the split datasets
    filtered_result.export(export_path, "coco_instances", save_media=True)
    
    return export_path, stats_annotations_path


def main():
    st.write("# Filter Annotation")
    images = st.file_uploader(
        "Upload Image Files", accept_multiple_files=True, type=["jpg", "png", "jpeg"]
    )
    annotation = st.file_uploader("Upload Annotation File", type=["json", "xml"])

    if "task_path" not in st.session_state:
        st.session_state.task_path = None
    if "s3_uri" not in st.session_state:
        st.session_state.s3_uri = ""
    if "s3_comment" not in st.session_state:
        st.session_state.s3_comment = ""
    if "filter_cmd" not in st.session_state:
        st.session_state.filter_cmd = ""

    split_option = st.checkbox("Split after merging?", value=True)  # Add this line

    # Add the dropdown menu for selecting job type
    job_type = st.selectbox(
        "Select Annotation Type", ["instances", "keypoints", "segmentation"]
    )

    st.divider()
    sample_code = """
def filter_func(item: DatasetItem) -> bool:
    h, w = item.media_as(Image).size
    return w > 2048
    """
    st.code(sample_code)
    st.text("Above is a sample code to filter. You can apply your own below.")

    st.session_state.filter_cmd = st.text_area(
        "Define your filter function:",
        value=st.session_state.filter_cmd,
        height=300,
    )

    if st.button("Register Annotation"):
        if images and annotation and st.session_state.filter_cmd:
            base_path, now = save_uploaded_files(images, annotation, job_type)
            task_path, annotations_path = create_new_task_filter(
                base_path,
                now,
                filter_cmd=st.session_state.filter_cmd,
                split_option=split_option,
            )
            st.session_state.task_path = task_path
            st.success(f"New task created at {task_path}.")
            st.session_state.now = now
            
            # Show category statistics after filtering
            st.divider()
            st.write("## Category Statistics After Filtering")
            try:
                with open(annotations_path, 'r') as f:
                    coco_data = json.load(f)
                show_category_statistics(coco_data)
            except Exception as e:
                st.error(f"Error loading COCO file for statistics: {e}")
        else:
            st.error("Please upload images, annotations, and define a filter function.")

    if st.session_state.task_path:
        st.session_state.s3_uri = st.text_input(
            "Enter S3 URI to upload (e.g., s3://hexa-cv-dataset/test/)",
            value=st.session_state.s3_uri,
            on_change=lambda: setattr(
                st.session_state, "s3_uri", st.session_state.s3_uri
            ),
        )
        st.session_state.s3_comment = st.text_input(
            "Enter Comment for S3 dataset (e.g., cross_validation)",
            value=st.session_state.s3_comment,
            on_change=lambda: setattr(
                st.session_state, "s3_comment", st.session_state.s3_comment
            ),
        )
        if st.button("Upload to S3"):
            if len(st.session_state.s3_uri) == 0:
                st.warning("Write S3 URI.")
            else:
                upload_to_s3(
                    st.session_state.task_path,
                    st.session_state.s3_uri,
                    st.session_state.now,
                    st.session_state.s3_comment,
                )
                st.success(f"Data uploaded to S3 at {st.session_state.s3_uri}")
                
                # Show category statistics after upload
                st.divider()
                st.write("## Category Statistics of Uploaded Data")
                try:
                    annotations_path = os.path.join(st.session_state.task_path, "annotations", "instances_default.json")
                    with open(annotations_path, 'r') as f:
                        coco_data = json.load(f)
                    show_category_statistics(coco_data)
                except Exception as e:
                    st.error(f"Error loading COCO file for statistics: {e}")
    elif st.button("Upload to S3"):
        st.warning("First create a task before uploading to S3.")
        
    # Add a button to show category statistics independently
    if st.session_state.task_path and st.button("Show Category Statistics"):
        st.divider()
        st.write("## Category Statistics")
        try:
            annotations_path = os.path.join(st.session_state.task_path, "annotations", "instances_default.json")
            with open(annotations_path, 'r') as f:
                coco_data = json.load(f)
            show_category_statistics(coco_data)
        except Exception as e:
            st.error(f"Error loading COCO file for statistics: {e}")


main()
