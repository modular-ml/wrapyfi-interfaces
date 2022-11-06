

class DlibFaceDetection(object):
    def __init__(self):
        import face_recognition
        self.__face_recognition__ = face_recognition

    def detect_bboxes(self, video_frames_list, match_face=None, **kwargs):
        # loading the features for tracking
        if match_face is not None:
            p_image = self.__face_recognition__.load_image_file(match_face)  # match_face is a path to an image
            p_encoding = self.__face_recognition__.face_encodings(p_image)[0]

        faces_locations = []
        for f_idx in range(len(video_frames_list)):
            # detecting the person inside the image if specified
            if video_frames_list[f_idx] is not None:
                boxes = self.__face_recognition__.face_locations(video_frames_list[f_idx])
                if match_face is not None:
                    tmp_encodings = self.__face_recognition__.face_encodings(video_frames_list[f_idx])
                    results = self.__face_recognition__.compare_faces(tmp_encodings, p_encoding)
                    for id, box in enumerate(boxes):
                        if results[id]:
                            boxes = [box]
                            break
                faces_locations.append(boxes)
            else:
                faces_locations.append([])
        return faces_locations


class MTCNNFaceDetection(object):
    def __init__(self, device="cuda:0"):
        from facenet_pytorch import MTCNN
        import numpy as np
        self.__mtcnn__ = MTCNN(keep_all=True, device=device)
        self.__np__ = np

    def detect_bboxes(self, video_frames_list, **kwargs):
        faces_locations = []
        for f_idx in range(len(video_frames_list)):
            # detect faces
            boxes = []
            if video_frames_list[f_idx] is not None:
                box_vals, _ = self.__mtcnn__.detect(video_frames_list[f_idx])
                if box_vals is not None:
                    for box in box_vals:
                        (left, top, right, bottom) = box.astype(self.__np__.int32).tolist()
                        boxes.append([top, right, bottom, left])
            faces_locations.append(boxes)
        return faces_locations


class SFDFaceDetection:
    def __init__(self, filter_threshold=0.5, device='cuda:0', verbose=False):
        import torch
        import torch.backends.cudnn as cudnn
        from face_alignment.detection.sfd import FaceDetector
        import numpy as np
        self.__torch__ = torch
        self.__np__ = np
        self.device = device
        self.verbose = verbose

        if 'cuda' in device:
            cudnn.benchmark = True

        # Get the face detector
        self.face_detector = FaceDetector(device=device, filter_threshold=filter_threshold, verbose=verbose)

    def detect_bboxes(self, video_frames_list, **kwargs):
        # images = self.__np__.asarray(video_frames_list)[..., ::-1]
        # images = self.__np__.squeeze(images, axis=1)
        # images = self.__torch__.FloatTensor(images)
        images = self.__np__.moveaxis(self.__np__.stack(video_frames_list), -1, 1)
        images =  self.__torch__.from_numpy(images).to(device=self.device)
        detected_faces = self.face_detector.detect_from_batch(images)
        face_locations = []

        for i, d in enumerate(detected_faces):
            if len(d) == 0:
                face_locations.append([])
                continue
            boxes = []
            for b in d:
                b = self.__np__.clip(b, 0, None)
                x1, y1, x2, y2 = map(int, b[:-1])
                boxes.append([y1, x2, y2, x1])
            face_locations.append(boxes)
        return face_locations


class BlazeFaceDetection:
    def __init__(self, min_score_threshold=0.5, min_suppression_threshold=0.5, device='cuda:0', verbose=False):
        import torch
        import torch.backends.cudnn as cudnn
        from face_alignment.detection.blazeface import FaceDetector
        import numpy as np
        self.__torch__ = torch
        self.__np__ = np
        self.device = device
        self.verbose = verbose

        if 'cuda' in device:
            cudnn.benchmark = True

        # Get the face detector
        self.face_detector = FaceDetector(device=device,
                                          min_score_thresh=min_score_threshold,
                                          min_suppression_threshold=min_suppression_threshold,
                                          verbose=verbose)

    def detect_bboxes(self, video_frames_list, **kwargs):
        # images = self.__np__.asarray(video_frames_list)[..., ::-1]
        # images = self.__np__.squeeze(images, axis=1)
        # images = self.__torch__.FloatTensor(images)
        images = self.__np__.moveaxis(self.__np__.stack(video_frames_list), -1, 1)
        images =  self.__torch__.from_numpy(images).to(device=self.device)
        detected_faces = self.face_detector.detect_from_batch(images)
        face_locations = []

        for i, d in enumerate(detected_faces):
            if len(d) == 0:
                face_locations.append([])
                continue
            boxes = []
            for b in d:
                b = self.__np__.clip(b, 0, None)
                x1, y1, x2, y2 = map(int, b[:-1])
                boxes.append([y1, x2, y2, x1])
            face_locations.append(boxes)
        return face_locations


# TODO (fabawi): add face detector from https://github.com/elliottzheng/face-detection
class RetinaFaceDetection:
    def __init__(self):
        pass

    def detect_bboxes(self, video_frames_list, **kwargs):
        pass