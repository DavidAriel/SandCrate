# import cProfile, pstats, io
# pr = cProfile.Profile()
# pr.enable()

import pygame
import time
import random
import numpy as np
# import numpy.linalg


def rand_vec():
    return np.random.rand(2)

DT = 0.005
R = 0.01
DIAMETER = R * 2

PARTICLE_MASS = 0.3
PRESSURE_AMPLIFIER = 7
IGNORED_PRESSURE = 0.1
VISCOSITY = 2
TENSILE_ALPHA = 5
TENSILE_BETA = 3 #droplets factor

TARGET_FRAME_RATE = 120
PARTICLE_COUNT = 500
MAX_COLLIDERS = 6
SCREEN_X = 500
SCREEN_Y = 500



class Crate(object):
    g = np.array([0.0, 9.81])
    screen = pygame.display.set_mode((SCREEN_X, SCREEN_Y))
    pygame.display.set_caption("SandCrate")
    clock = pygame.time.Clock()

    def __init__(self):
        self.colliders = [None] * PARTICLE_COUNT
        self.colliders_indice = [[]] * PARTICLE_COUNT
        self.gen_particles()


    def gen_particles(self):
        self.particles = np.zeros((PARTICLE_COUNT, 8))
        # random position [0, 1) and velocities[-1, 1] on startup
        self.particles[:, 0: 2] = np.random.rand(PARTICLE_COUNT, 4)


    def get_particle_location(self, x, y):
        return int(x * (SCREEN_X-1)), int(y * (SCREEN_Y-1))

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    self.gen_particles()
                if event.key == pygame.K_RIGHT:
                    self.g = np.array([9.81, 0.0])
                if event.key == pygame.K_LEFT:
                    self.g = np.array([-9.81, 0.0])
                if event.key == pygame.K_q:
                    self.done = True
            if event.type == pygame.KEYUP:
                self.g = np.array([0.0, 9.81])
            if event.type == pygame.QUIT:
                self.done = True


    def physics_tick(self):

        self.detect_collisions()
        self.precalc_colliders_interaction()
        self.copy_to_colliders_mats()
        self.apply_velocities_updates()
        self.apply_positions_updates()


    def display_particles(self):
        BLUE = (0, 0, 255)
        RED = (255, 0, 0)
        BLACK = (0, 0, 0)
        # buffer = np.zeros((SCREEN_X, SCREEN_Y))
        p_rad = int(SCREEN_X * R)
        self.screen.fill(BLACK)
        self.particles[:, 5] /= np.max(self.particles[:, 5])
        for i in range(self.particles.shape[0]):
            center = self.get_particle_location(self.particles[i, 0], self.particles[i, 1])
            color = (255 - int(self.particles[i, 5] * 255), 255 - int(self.particles[i, 5] * 255), 255)
            pygame.draw.circle(self.screen, color , center, p_rad)
            # buffer[center[0] - p_rad: center[0] + p_rad, center[1] - p_rad: center[1] + p_rad] = 1
        # buffer = 255 * buffer / buffer.max()
        # surf = pygame.surfarray.make_surface(buffer)
        # self.screen.blit(surf, (0, 0))
        pygame.display.update()

    def detect_collisions(self):
        y_floored = np.floor(self.particles[:, 1] / DIAMETER)
        sorted_inds = np.lexsort((self.particles[:, 0], y_floored))
        self.particles = self.particles[sorted_inds, :]
        y_floored = y_floored[sorted_inds]
        unique_ys, unique_inds = np.unique(y_floored, return_index=True)
        unique_inds = np.append(unique_inds, len(y_floored))
        next_strip = self.particles[unique_inds[0]: unique_inds[1], 0]
        for i in range(len(unique_inds) - 1):
            strip = next_strip
            # strip = self.particles[unique_inds[i]: unique_inds[i + 1], 1]
            next_strip = [] if i == len(unique_inds) - 2 else self.particles[unique_inds[i + 1]: unique_inds[i + 2], 0]
            for j, x in enumerate(strip):
                end = np.searchsorted(strip, x + DIAMETER, side='right')
                j_colliders = [k for k in range(unique_inds[i] + j + 1, unique_inds[i] + end)]

                if i + 1 < len(unique_ys) and unique_ys[i] + 1 == unique_ys[i + 1]:
                    next_start = np.searchsorted(next_strip, x - DIAMETER, side='left')
                    next_end = np.searchsorted(next_strip, x + DIAMETER, side='right')
                    new_indices = [k for k in range(unique_inds[i + 1] + next_start, unique_inds[i + 1] + next_end)]
                    too_far = ((self.particles[new_indices, 0] - self.particles[unique_inds[i] + j, 0]) ** 2
                              + (self.particles[new_indices, 1] - self.particles[unique_inds[i] + j, 1]) ** 2) <= DIAMETER ** 2
                    new_indices = [k for t, k in enumerate(new_indices) if too_far[t]]
                    j_colliders += new_indices
                self.colliders_indice[unique_inds[i] + j] = j_colliders[:MAX_COLLIDERS]
        self.reverse_link_colliders()

    def reverse_link_colliders(self):
        for i in range(PARTICLE_COUNT):
            for j in self.colliders_indice[i]:
                self.colliders_indice[j].append(i)
        for i in range(PARTICLE_COUNT):
            self.colliders_indice[i] = list(set(self.colliders_indice[i]))

    def add_wall_virtual_colliders(self, i):
        WALL_FAKE_OVERLAP = 0.9
        if self.particles[i, 0] <= R:
            virtual_particle = np.zeros((1, 9))
            virtual_particle[0, 0] = DIAMETER * WALL_FAKE_OVERLAP
            virtual_particle[0, 5: 9] = [1 - WALL_FAKE_OVERLAP, (1 - WALL_FAKE_OVERLAP - IGNORED_PRESSURE) * PRESSURE_AMPLIFIER, DIAMETER * WALL_FAKE_OVERLAP * WALL_FAKE_OVERLAP * (1 - WALL_FAKE_OVERLAP), 0]
            self.colliders[i] = np.vstack([self.colliders[i], virtual_particle])

        if self.particles[i, 0] >= 1 - R:
            virtual_particle = np.zeros((1, 9))
            virtual_particle[0, 0] = -DIAMETER * WALL_FAKE_OVERLAP
            virtual_particle[0, 5: 9] = [1 - WALL_FAKE_OVERLAP, (1 - WALL_FAKE_OVERLAP - IGNORED_PRESSURE) * PRESSURE_AMPLIFIER, -DIAMETER * WALL_FAKE_OVERLAP * WALL_FAKE_OVERLAP * (1 - WALL_FAKE_OVERLAP), 0]
            self.colliders[i] = np.vstack([self.colliders[i], virtual_particle])

        if self.particles[i, 1] <= R:
            virtual_particle = np.zeros((1, 9))
            virtual_particle[0, 1] = DIAMETER * WALL_FAKE_OVERLAP
            virtual_particle[0, 5: 9] = [1 - WALL_FAKE_OVERLAP, (1 - WALL_FAKE_OVERLAP - IGNORED_PRESSURE) * PRESSURE_AMPLIFIER, 0, DIAMETER * WALL_FAKE_OVERLAP * WALL_FAKE_OVERLAP * (1 - WALL_FAKE_OVERLAP)]
            self.colliders[i] = np.vstack([self.colliders[i], virtual_particle])

        if self.particles[i, 1] >= 1 - R:
            virtual_particle = np.zeros((1, 9))
            virtual_particle[0, 1] = -DIAMETER * WALL_FAKE_OVERLAP
            virtual_particle[0, 5: 9] = [1 - WALL_FAKE_OVERLAP, (1 - WALL_FAKE_OVERLAP - IGNORED_PRESSURE) * PRESSURE_AMPLIFIER, 0, -DIAMETER * WALL_FAKE_OVERLAP * WALL_FAKE_OVERLAP * (1 - WALL_FAKE_OVERLAP)]
            self.colliders[i] = np.vstack([self.colliders[i], virtual_particle])

    def precalc_colliders_interaction(self):
        NOISE_LEVEL = 0.2
        ONTOP_FAKE_DISTANCE = 0.9
        for i in range(PARTICLE_COUNT):
            self.colliders[i] = np.zeros((len(self.colliders_indice[i]), 9))
            self.colliders[i][:, 0: 2] = self.particles[i, 0: 2] - self.particles[self.colliders_indice[i], 0: 2]
            self.colliders[i][:, 0: 2] += (np.random.rand(self.colliders[i].shape[0], 2) - 0.5) * DIAMETER * NOISE_LEVEL

            self.add_wall_virtual_colliders(i)
            if self.colliders[i].shape[0] == 0:
                continue

            ontop_mask = np.logical_and(self.colliders[i][:, 0] == 0, self.colliders[i][:, 1] == 0)
            if np.sum(ontop_mask) > 0:
                self.colliders[i][ontop_mask, 0: 2] = (np.random.rand(1,2) - 0.5) * ONTOP_FAKE_DISTANCE * DIAMETER

            self.colliders[i][:, 2] = np.sqrt(self.colliders[i][:, 0] ** 2 + self.colliders[i][:, 1] ** 2)
            self.colliders[i][:, 0: 2] /= self.colliders[i][:, 2: 3]  # normalized repel from collider
            self.colliders[i][:, 2] = 1 - self.colliders[i][:, 2] / DIAMETER  # collider particle overlap
            self.colliders[i][:, 2] = np.minimum(1, np.maximum(0, self.colliders[i][:, 2]))  # collider particle overlap
            self.particles[i, 4] = np.sum(self.colliders[i][:, 2], 0)  # total overlap
            # assert np.all(self.particles[i, 4] >= 0)
            self.particles[i, 5] = np.maximum(0, (self.particles[i, 4] - IGNORED_PRESSURE) * PRESSURE_AMPLIFIER)  # pressure
            # mid-range pressure
            self.particles[i, 6: 8] = np.sum(self.colliders[i][:, 0: 2] * (1 - self.colliders[i][:, 2: 3]) * (self.colliders[i][:, 2: 3]), 0)

    def copy_to_colliders_mats(self):
        for i in range(PARTICLE_COUNT):
            self.colliders[i][0: len(self.colliders_indice[i]), 3 : 9] = self.particles[self.colliders_indice[i], 2: 8]


    def apply_velocities_updates(self):
        # gravity
        self.particles[:, 2: 4] += DT * self.g * PARTICLE_MASS
        for i in range(PARTICLE_COUNT):
            if self.colliders[i].shape[0] == 0:
                continue

            # pressure - dt * (particle_presure + collider_presure) * collider_relative_overlap * normalized_repel
            self.particles[i, 2: 4] += DT * np.sum((self.particles[i, 5: 6] + self.colliders[i][:, 6: 7]) * self.colliders[i][:, 2: 3] * self.colliders[i][:, 0: 2], 0)
            # viscosity
            self.particles[i, 2: 4] += DT * VISCOSITY * np.sum(self.colliders[i][:, 3: 5] - self.particles[i, 2: 4], 0)
            # surface tension
            a = TENSILE_ALPHA * (self.particles[i, 4] + self.colliders[i][:, 5: 6] - 2 * IGNORED_PRESSURE)
            b = TENSILE_BETA * (np.sum((self.colliders[i][:, 7: 9] - self.particles[i, 6: 8]) * self.colliders[i][:, 0: 2], 1)[:, None])
            self.particles[i, 2: 4] += DT * np.sum(self.colliders[i][:, 0: 2] * (a + b), 0)

    def apply_positions_updates(self):
        self.particles[:, 0: 2] += DT * self.particles[:, 2: 4]


        # self.particles[np.logical_or(self.particles[:, 0] <= 0, self.particles[:, 0] >= 1), 2] *= -ELASTICITY
        # self.particles[np.logical_or(self.particles[:, 1] <= 0, self.particles[:, 1] >= 1), 3] *= -ELASTICITY
        # self.particles[np.logical_or(self.particles[:, 0] <= R, self.particles[:, 0] >= 1 - R), 2] = 0
        # self.particles[np.logical_or(self.particles[:, 1] <= R, self.particles[:, 1] >= 1 - R), 3] = 0
        self.particles[:, 0: 2] = np.maximum(self.particles[:, 0: 2], R)
        self.particles[:, 0: 2] = np.minimum(self.particles[:, 0: 2], 1 - R)

    def run_main_loop(self):
        self.done = False
        while not self.done:
            self.clock.tick(TARGET_FRAME_RATE)
            self.handle_input()
            self.physics_tick()
            self.display_particles()
        pygame.quit()



crate = Crate()
crate.run_main_loop()

# pr.disable()
# s = io.StringIO()
# sortby = 'cumulative'
# ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
# ps.print_stats()
# print(s.getvalue())

