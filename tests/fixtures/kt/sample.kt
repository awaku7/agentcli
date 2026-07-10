package com.myapp.core

import kotlinx.coroutines.Deferred

/**
 * Person data class.
 */
data class Person(val name: String, val age: Int) {
    val greeting: String get() = "Hello, $name"

    suspend fun processAsync(id: Int, data: String): Result {
        return doWork(id, data)
    }

    override fun toString(): String = "$name ($age)"
}

/**
 * Generic repository interface.
 */
interface Repository<T> {
    suspend fun getById(id: Int): T
    suspend fun save(entity: T)
}

enum class Status { ACTIVE, INACTIVE, PENDING }

/**
 * Sealed class example.
 */
sealed class NetworkResult<out T> {
    data class Success<T>(val data: T) : NetworkResult<T>()
    data class Error(val message: String) : NetworkResult<Nothing>()
}

object PersonFactory {
    fun create(name: String, age: Int) = Person(name, age)
}

fun String.greet(): String = "Hi, $this!"
