import pickle
import copy
import os
import sys
import numpy as np
import cv2
import dlib
import modules.util as util
from modules.regression_tree import RegressionTree
from modules.face_model import ShapeModel
from multiprocessing import Pool, Process, cpu_count
from modules.procrustes import calculate_procrustes, mean_of_shapes, root_mean_square
from scipy.spatial.distance import cdist as distance
from imutils import resize

cap = cv2.VideoCapture(0)
detector = dlib.get_frontal_face_detector()

with open('reg.bin', 'rb') as f:
    regressors = pickle.load(f)

with open('model.bin', 'rb') as f:
    model = pickle.load(f)

with open('sample_points.bin', 'rb') as f:
    sample_points = pickle.load(f)

def warp(shape_a, shape_b, groups):
    scale, angle, _ = util.similarity_transform(shape_b, shape_a)
    new_groups = np.zeros(groups.shape)
    for i, group in enumerate(groups):
        for j, point in enumerate(group):
            offset = point - shape_a[i]
            offset = util.rotate(offset / scale, -angle)
            new_groups[i][j] = shape_b[i] - offset
    return new_groups

while True:
    _, img = cap.read()
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = detector(img)
    for face in faces:
        top_left = (face.left(), face.top())
        bottom_right = (face.right(), face.bottom())
        pivot = ((np.array(top_left) + np.array(bottom_right)) / 2)
        scale = face.width() * 0.3

        first_estimation = model.base_shape * scale + pivot
        test_estimation = model.base_shape * scale + pivot
        test_sample_points = sample_points * scale + pivot
        
        for regressor in regressors:
            intensity_data = []
            for group in test_sample_points:
                intensity_group = []
                for point in group:
                    y, x = np.array(point).astype(int)
                    try:
                        intensity = img.item(x, y)
                        intensity_group.append(intensity)
                    except IndexError:
                        intensity_group.append(-1)
                intensity_data.append(intensity_group)

            test_estimation_norm = (test_estimation - pivot) / scale
            params_estimation = model.retrieve_parameters(test_estimation_norm)
            for tree in regressor:
                index = tree.apply(intensity_data)
                delta_params = tree.predictions[index]
                params_estimation += delta_params * 0.1
            new_estimation = model.deform(params_estimation)
            new_estimation = (new_estimation * scale + pivot)

            # Update sample points and estimation
            test_sample_points = warp(test_estimation, new_estimation, test_sample_points)
            test_estimation = new_estimation

        util.plot(img, test_estimation)
        # util.plot(img, test_sample_points.flatten().reshape([3 * len(model.base_shape), 2]))

    img = resize(img, height=800)
    cv2.imshow('frame', img)
    key = cv2.waitKey(30) & 0xFF
    if key == 27:
        break