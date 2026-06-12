class PoseCapError(Exception):
    """Base for all domain errors raised by core (GUIDELINES §2.2).

    Adapters translate these at their edges — Operator.report on the bpy
    side, structured logs plus job status on the engine side.
    """
