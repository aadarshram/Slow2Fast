;; Typed gripper: a robot with two grippers moves balls between rooms. Used to check the PDDL layer is
;; domain-independent; typing is compiled into unary predicates by cmc/pddl.py.
(define (domain gripper)
  (:requirements :strips :typing)
  (:types room ball gripper)
  (:predicates (at-robby ?r - room) (at ?b - ball ?r - room) (free ?g - gripper) (carry ?b - ball ?g - gripper))

  (:action move
    :parameters (?from - room ?to - room)
    :precondition (at-robby ?from)
    :effect (and (at-robby ?to) (not (at-robby ?from))))

  (:action pick
    :parameters (?b - ball ?r - room ?g - gripper)
    :precondition (and (at ?b ?r) (at-robby ?r) (free ?g))
    :effect (and (carry ?b ?g) (not (at ?b ?r)) (not (free ?g))))

  (:action drop
    :parameters (?b - ball ?r - room ?g - gripper)
    :precondition (and (carry ?b ?g) (at-robby ?r))
    :effect (and (at ?b ?r) (free ?g) (not (carry ?b ?g))))
)
